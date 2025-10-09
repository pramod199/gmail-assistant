import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.routers.websocket import VoiceWebSocketHandler
from app.routers.websocket_helpers import safe_websocket_close, send_json_safe
from app.services.voice_session_manager import voice_session_manager

logger = logging.getLogger(__name__)

router = APIRouter()
voice_handler = VoiceWebSocketHandler()


@router.websocket("/voice")
async def voice_websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(...),
    firebase_user_id: str = Query(...)
):
    """
    WebSocket endpoint for streaming voice processing with session-based architecture.

    Requires:
    - session_id: Created via POST /api/sessions
    - firebase_user_id: Authenticated Firebase user

    Each session is isolated with:
    - Gmail credentials and navigation state
    - Gemini Live API session
    - Redis session persistence

    Note: Firebase authentication is handled at app level
    """
    user_id = None

    try:
        logger.info(f"WebSocket connection attempt for user {firebase_user_id}, session {session_id}")

        # Connect with pre-validated Firebase user ID and session
        user_id = await voice_handler.connect(websocket, firebase_user_id, session_id)

        if not user_id:
            logger.error(f"Failed to establish connection - no user_id returned for session {session_id}")
            return

        logger.info(f"WebSocket connection established for user {user_id}, session {session_id}")

        # Message processing loop for this session
        while True:
            try:
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)

                # Process message for this specific user and session
                await voice_handler.handle_message(websocket, user_id, session_id, message)

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}, session {session_id}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {user_id}: {e}")
                await send_json_safe(websocket, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Message processing error for user {user_id}, session {session_id}: {e}")
                await send_json_safe(websocket, {
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                })

    except Exception as e:
        logger.error(f"WebSocket connection failed for session {session_id}: {e}")

    finally:
        # Cleanup session and close WebSocket
        if user_id and session_id:
            logger.info(f"Cleaning up session {session_id} for user {user_id}")
            voice_session = await voice_session_manager.get_session(session_id)
            if voice_session:
                voice_session.active = False
                await voice_session_manager.update_session(voice_session)

            # Close WebSocket safely
            await safe_websocket_close(websocket)