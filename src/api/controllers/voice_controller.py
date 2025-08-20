import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ..middleware.auth import verify_firebase_token
from ..websocket.voice_handler import VoiceWebSocketHandler

logger = logging.getLogger(__name__)

router = APIRouter()
voice_handler = VoiceWebSocketHandler()


@router.websocket("/voice")
async def voice_websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket endpoint for streaming voice processing
    Each user gets their own isolated connection with separate:
    - Authentication (Firebase token)
    - Gmail credentials and session
    - Gemini Live API session
    - Redis session state
    """
    user_id = None
    
    try:
        logger.info("WebSocket connection attempt")
        
        # Let the handler manage authentication and WebSocket accept
        user_id = await voice_handler.connect(websocket, token)
        
        if not user_id:
            logger.error("Failed to establish connection - no user_id returned")
            return
        
        logger.info(f"WebSocket connection established for user {user_id}")
        
        # Message processing loop for this user's connection
        while True:
            try:
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)
                
                # Process message for this specific user
                await voice_handler.handle_message(websocket, user_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {user_id}: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Message processing error for user {user_id}: {e}")
                await websocket.send_json({
                    "type": "error", 
                    "message": f"Processing error: {str(e)}"
                })
    
    except Exception as e:
        logger.error(f"WebSocket connection failed: {e}")
    
    finally:
        # Cleanup this user's connection
        if user_id:
            await voice_handler.disconnect(user_id)