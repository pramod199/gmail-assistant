"""
WebSocket endpoint for audio-only streaming (following auto-translator-server architecture)

Protocol: Pure binary audio streaming
- Client sends: Raw PCM audio bytes (16kHz, 16-bit, mono)
- Server sends: Raw PCM audio bytes from Gemini Live API
- Control messages: Handled via separate HTTP endpoints

Multi-user safe: All state is per-session, functions are stateless
"""
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from starlette.websockets import WebSocketState

from app.routers.websocket import (
    handle_incoming_audio,
    handle_outgoing_audio,
    create_gmail_service
)
from app.routers.websocket_helpers import safe_websocket_close
from app.services.voice_session_manager import voice_session_manager
from app.services.gmail_oauth_service import UserCredentialStore
from app.services.gemini_service import GeminiLiveClient
from app.services.function_handler import GmailFunctionHandler
from app.services.session_service import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter()
credential_store = UserCredentialStore()
session_manager = SessionManager()


@router.websocket("/ws/{session_id}")
async def voice_websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    firebase_user_id: str = Query(...)
):
    """
    WebSocket endpoint for audio-only streaming (following reference architecture).

    **Protocol:**
    - Client → Server: Raw PCM audio bytes (16kHz, 16-bit, mono)
    - Server → Client: Raw PCM audio bytes (Gemini Live API responses)

    **Control Flow:**
    1. Create session: POST /api/sessions
    2. Connect WebSocket: ws://host/api/ws/{session_id}?firebase_user_id={uid}
    3. Start voice session: POST /api/sessions/{session_id}/voice/start
    4. Stream audio: Send/receive raw bytes over WebSocket
    5. Stop voice session: POST /api/sessions/{session_id}/voice/stop
    6. Cleanup: DELETE /api/sessions/{session_id}

    **Multi-user Safe:**
    - All state stored per-session in Redis
    - No shared state between users
    - Stateless handler functions
    """
    user_id = firebase_user_id
    voice_session = None

    try:
        logger.info(f"WebSocket connection attempt for user {user_id}, session {session_id}")

        # Validate user ID - MUST validate before accept()
        if not user_id:
            logger.warning(f"WebSocket rejected: Invalid user ID")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Validate voice session exists and is active
        voice_session = await voice_session_manager.get_session(session_id)
        if not voice_session:
            logger.warning(f"WebSocket rejected: Session not found {session_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if not voice_session.active:
            logger.warning(f"WebSocket rejected: Session {session_id} is not active")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Validate session ownership
        if voice_session.user_id != user_id:
            logger.warning(f"WebSocket rejected: User {user_id} tried to access session {session_id} owned by {voice_session.user_id}")
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        # All validation passed - accept WebSocket connection
        await websocket.accept()
        logger.info(f"✅ WebSocket connection established for session {session_id}, user {user_id}")

        # Get user's Gmail credentials from Redis
        gmail_credentials = await credential_store.get_credentials(user_id)
        if not gmail_credentials:
            logger.warning(f"Gmail auth not found for user {user_id} - voice session can be started after authorization")
            # Don't close connection - user can authorize via HTTP and then start voice session

        # Initialize services for this session (stateless pattern)
        gmail_service = create_gmail_service(gmail_credentials, user_id) if gmail_credentials else None
        function_handler = GmailFunctionHandler(gmail_service, session_manager, user_id) if gmail_service else None
        gemini_client = GeminiLiveClient()

        # Store services in voice session object (per-session state)
        voice_session.websocket = websocket
        voice_session.gmail_service = gmail_service
        voice_session.function_handler = function_handler
        voice_session.gemini_client = gemini_client

        # Create concurrent tasks for bidirectional audio streaming (like reference)
        tasks = set()
        incoming_task = asyncio.create_task(handle_incoming_audio(websocket, voice_session))
        outgoing_task = asyncio.create_task(handle_outgoing_audio(websocket, voice_session))
        tasks.update([incoming_task, outgoing_task])

        # Wait for any task to complete (first to finish triggers cleanup)
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Handle completed tasks
        for task in done:
            try:
                await task
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}, user {user_id}")
            except Exception as e:
                logger.error(f"WebSocket task for session {session_id}, user {user_id} completed with error: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket (outer handler) disconnected for session {session_id}, user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}, user {user_id}: {e}")
    finally:
        # Cleanup session (following reference architecture)
        if voice_session:
            voice_session.active = False
            await voice_session_manager.update_session(voice_session)

            # Close Gemini session if active
            if voice_session.session_context and voice_session.gemini_session:
                try:
                    await voice_session.session_context.__aexit__(None, None, None)
                    logger.info(f"Closed Gemini session for {session_id}")
                except Exception as e:
                    logger.error(f"Error closing Gemini session for {session_id}: {e}")

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
                    logger.debug(f"Task {i} in WebSocket for session {session_id} encountered disconnection during cleanup")
                elif isinstance(result, Exception):
                    error_str = str(result).lower()
                    if "1000" in error_str or "1001" in error_str or "going away" in error_str:
                        logger.debug(f"Task {i} in WebSocket for session {session_id} closed normally during cleanup")
                    else:
                        logger.error(f"Task {i} in WebSocket for session {session_id} raised an unexpected exception during cleanup: {result}")

        await safe_websocket_close(websocket)
        logger.info(f"WebSocket connection closed and cleaned up for session {session_id}, user {user_id if user_id else 'unknown'}")
