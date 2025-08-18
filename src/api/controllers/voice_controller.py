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
    user_info = None
    
    try:
        # Authenticate this user using the same logic as HTTP middleware
        user_info = verify_firebase_token(token)
        user_id = user_info["user_id"]
        
        logger.info(f"WebSocket authentication successful for user {user_id}")
        
        # Establish connection for this specific user
        await voice_handler.connect(websocket, token)
        
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
        logger.error(f"WebSocket authentication failed: {e}")
        try:
            await websocket.close(code=4001, reason="Authentication failed")
        except:
            pass
    
    finally:
        # Cleanup this user's connection
        if user_info:
            await voice_handler.disconnect(user_info["user_id"])