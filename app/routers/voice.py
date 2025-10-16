import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from starlette.websockets import WebSocketState

from app.services.gemini_service import GeminiLiveClient
from app.services.function_handler import GmailFunctionHandler
from app.services.gmail_service import GmailService
from app.services.session_service import SessionManager
from app.services.voice_session_manager import voice_session_manager
from app.services.gmail_oauth_service import UserCredentialStore
from app.routers.websocket import handle_incoming_audio, handle_outgoing_audio
from app.routers.websocket_helpers import safe_websocket_close, send_json_safe

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/voice")
async def voice_websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(...),
    firebase_user_id: str = Query(...)
):
    """
    WebSocket endpoint for voice assistant with streaming audio processing.

    Following auto-translator pattern:
    - Accepts connection first, then validates
    - Uses simple task-based architecture
    - Sends raw bytes for audio (not JSON)
    - Proper task cleanup in finally block
    """
    # Accept connection first
    await websocket.accept()

    # Validate session
    voice_session = await voice_session_manager.get_session(session_id)
    if not voice_session:
        await safe_websocket_close(websocket, code=status.WS_1008_POLICY_VIOLATION, reason="Session not found")
        logger.warning(f"WebSocket connection attempt for non-existent session: {session_id}")
        return

    if not voice_session.active:
        await safe_websocket_close(websocket, code=status.WS_1008_POLICY_VIOLATION, reason="Session is not active")
        logger.warning(f"WebSocket connection attempt for inactive session: {session_id}")
        return

    # Validate session ownership
    if voice_session.user_id != firebase_user_id:
        await safe_websocket_close(websocket, code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized session access")
        logger.warning(f"User {firebase_user_id} attempted to access session {session_id} owned by {voice_session.user_id}")
        return

    # Get user's Gmail credentials
    credential_store = UserCredentialStore()
    gmail_credentials = await credential_store.get_credentials(firebase_user_id)
    if not gmail_credentials:
        logger.info(f"Gmail auth not found for user {firebase_user_id}")
        await send_json_safe(websocket, {
            "type": "error",
            "message": "Gmail authorization required. Please authorize Gmail access first.",
            "action_required": "gmail_auth",
            "auth_url": f"/api/auth/gmail/authorize"
        })
        await safe_websocket_close(websocket, code=status.WS_1008_POLICY_VIOLATION, reason="Gmail authorization required")
        return

    logger.info(f"WebSocket connection established for session {session_id}, user {firebase_user_id}")

    # Initialize services for this session
    session_manager = SessionManager()
    gmail_service = GmailService(gmail_credentials, firebase_user_id)
    function_handler = GmailFunctionHandler(gmail_service, session_manager, firebase_user_id)
    gemini_client = GeminiLiveClient()

    # Store services in voice session
    voice_session.websocket = websocket
    voice_session.gmail_service = gmail_service
    voice_session.function_handler = function_handler

    # Send connection success
    await send_json_safe(websocket, {
        "type": "connected",
        "message": "Voice assistant ready",
        "user_id": firebase_user_id,
        "session_id": session_id
    })

    tasks = set()

    try:
        # Initialize Gemini session in background task
        success = await gemini_client.initialize_session(
            voice_session,
            function_handler=function_handler.handle_function_call
        )

        if not success:
            await send_json_safe(websocket, {
                "type": "error",
                "message": "Failed to initialize Gemini session"
            })
            return

        await send_json_safe(websocket, {
            "type": "voice_session_started",
            "message": "Ready to receive audio"
        })

        logger.info(f"Voice session started for session {session_id}")

        # Start concurrent tasks (following auto-translator pattern)
        receive_task = asyncio.create_task(handle_incoming_audio(websocket, voice_session))
        send_task = asyncio.create_task(handle_outgoing_audio(websocket, voice_session))
        tasks.update([receive_task, send_task])

        # Wait for first task to complete
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Handle completed tasks
        for task in done:
            try:
                await task
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}, user {firebase_user_id}")
            except Exception as e:
                logger.error(f"WebSocket task for session {session_id}, user {firebase_user_id} completed with error: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket (outer handler) disconnected for session {session_id}, user {firebase_user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}, user {firebase_user_id}: {e}")
    finally:
        # Ensure session is marked as inactive
        if voice_session:
            voice_session.active = False
            await voice_session_manager.update_session(voice_session)

        # Close Gemini session (stops background task)
        if voice_session and gemini_client:
            await gemini_client.close_session(voice_session)

        # Cancel all tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, asyncio.CancelledError):
                    logger.debug(f"Task {i} in WebSocket for session {session_id} was cancelled as expected.")
                elif isinstance(result, WebSocketDisconnect):
                    logger.debug(f"Task {i} in WebSocket for session {session_id} encountered disconnection during cleanup: {result}")
                elif isinstance(result, Exception):
                    error_str = str(result).lower()
                    if "1000" in error_str or "1001" in error_str or "going away" in error_str:
                        logger.debug(f"Task {i} in WebSocket for session {session_id} closed normally during cleanup: {result}")
                    else:
                        logger.error(f"Task {i} in WebSocket for session {session_id} raised an unexpected exception during cleanup: {result}")

        await safe_websocket_close(websocket)
        logger.info(f"WebSocket connection closed and cleaned up for session {session_id}, user {firebase_user_id if firebase_user_id else 'unknown'}")
