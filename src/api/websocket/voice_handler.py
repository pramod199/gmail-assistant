import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect, HTTPException

from ...core.voice.gemini_live_client import GeminiLiveClient
from ...core.voice.function_handler import GmailFunctionHandler
from ...core.gmail_client.gmail_service import GmailService
from ...core.session.session_manager import SessionManager
from ...core.auth.user_credential_store import UserCredentialStore
from ..middleware.auth import verify_firebase_token


logger = logging.getLogger(__name__)


class VoiceWebSocketHandler:
    """Handle WebSocket connections for streaming voice processing"""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.credential_store = UserCredentialStore()
        self.active_connections: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, token: str):
        """Establish WebSocket connection with authentication"""
        try:
            # Validate Firebase token using the proper auth method
            user_info = verify_firebase_token(token)
            user_id = user_info["user_id"]
            user_email = user_info["user_email"]
            
            if not user_id:
                await websocket.close(code=4001, reason="Invalid user ID in token")
                return None
            
            # Accept WebSocket connection first
            await websocket.accept()
            logger.info(f"WebSocket accepted for user {user_id}")
            
            # Get user's Gmail credentials from Redis
            gmail_credentials = self.credential_store.get_credentials(user_id)
            if not gmail_credentials:
                # Send error message with auth URL before closing
                logger.info(f"gmail auth not found {user_id}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Gmail authorization required. Please authorize Gmail access first.",
                    "action_required": "gmail_auth",
                    "auth_url": f"/api/auth/gmail/authorize",
                    "user_id": user_id
                })
                await websocket.close(code=4002, reason="Gmail authorization required")
                return None
            
            # Initialize services for this user
            gmail_service = self._create_gmail_service(gmail_credentials)
            function_handler = GmailFunctionHandler(gmail_service, self.session_manager, user_id)
            
            # Initialize Gemini Live client
            gemini_client = GeminiLiveClient()
            
            # Store connection info
            self.active_connections[user_id] = {
                "websocket": websocket,
                "user_email": user_email,
                "gmail_service": gmail_service,
                "function_handler": function_handler,
                "gemini_client": gemini_client,
                "gemini_session": None
            }
            
            # Send connection success
            await websocket.send_json({
                "type": "connected",
                "message": "Voice assistant ready",
                "user_id": user_id,
                "user_email": user_email
            })
            
            logger.info(f"WebSocket connected for user {user_id} ({user_email})")
            return user_id
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            try:
                await websocket.close(code=4000, reason="Connection failed")
            except:
                pass
            return None
    
    async def handle_message(self, websocket: WebSocket, user_id: str, message: Dict[str, Any]):
        """Process incoming WebSocket message"""
        try:
            message_type = message.get("type")
            connection = self.active_connections.get(user_id)
            
            if not connection:
                await websocket.send_json({
                    "type": "error", 
                    "message": "Connection not found"
                })
                return
            
            if message_type == "start_voice_session":
                await self._start_voice_session(websocket, user_id, connection)
            
            elif message_type == "audio_chunk":
                await self._process_audio_chunk(websocket, user_id, connection, message)
            
            elif message_type == "end_voice_session":
                await self._end_voice_session(websocket, user_id, connection)
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
        
        except Exception as e:
            logger.error(f"Message handling error for user {user_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error processing message: {str(e)}"
            })
    
    async def _start_voice_session(self, websocket: WebSocket, user_id: str, connection: Dict[str, Any]):
        """Start a new Gemini Live voice session"""
        try:
            gemini_client: GeminiLiveClient = connection["gemini_client"]
            function_handler: GmailFunctionHandler = connection["function_handler"]
            
            # Get Gemini Live session context manager
            session_context = await gemini_client.create_session(
                function_handler=function_handler.handle_function_call
            )
            
            # Start the session using async context manager
            gemini_session = await session_context.__aenter__()
            
            connection["gemini_session"] = gemini_session
            connection["session_context"] = session_context  # Store context for cleanup
            connection["response_task"] = None  # Track response processing task
            
            # Start processing responses from Gemini with error handling
            await self._start_response_processing(websocket, user_id, connection)
            
            await websocket.send_json({
                "type": "voice_session_started",
                "message": "Ready to receive audio"
            })
            
            logger.info(f"Voice session started for user {user_id}")
        
        except Exception as e:
            logger.error(f"Failed to start voice session for user {user_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to start voice session: {str(e)}"
            })
    
    async def _process_audio_chunk(self, websocket: WebSocket, user_id: str, 
                                 connection: Dict[str, Any], message: Dict[str, Any]):
        """Process audio chunk from client"""
        try:
            gemini_session = connection.get("gemini_session")
            if not gemini_session:
                await websocket.send_json({
                    "type": "error",
                    "message": "No active voice session. Start session first."
                })
                return
            
            # Extract audio data
            audio_data = message.get("data")  # Base64 encoded audio
            audio_format = message.get("audio_format", {})
            mime_type = audio_format.get("mime_type", "audio/pcm;rate=16000")
            
            if not audio_data:
                return  # Ignore empty chunks
            
            # Decode base64 audio data
            import base64
            audio_bytes = base64.b64decode(audio_data)
            
            # Send to Gemini Live API
            gemini_client: GeminiLiveClient = connection["gemini_client"]
            await gemini_client.send_audio_chunk(gemini_session, audio_bytes, mime_type)
            
        except Exception as e:
            logger.error(f"Audio processing error for user {user_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Audio processing error: {str(e)}"
            })
    
    async def _start_response_processing(self, websocket: WebSocket, user_id: str, connection: Dict[str, Any]):
        """Start response processing with error handling and monitoring"""
        try:
            # Create and store the response processing task
            task = asyncio.create_task(self._process_gemini_responses(websocket, user_id, connection))
            connection["response_task"] = task
            
            # Monitor the task for completion (both normal and error cases)
            def task_done_callback(task):
                try:
                    if task.cancelled():
                        logger.info(f"Response processing task cancelled for user {user_id}")
                    elif task.exception():
                        logger.error(f"Response processing task failed for user {user_id}: {task.exception()}")
                    else:
                        logger.info(f"Response processing task completed normally for user {user_id}")
                    
                    # Always restart the task if WebSocket is still connected and not cancelled
                    # This handles both normal completion and errors
                    if user_id in self.active_connections and not task.cancelled():
                        logger.info(f"Scheduling restart of response processing for user {user_id}")
                        asyncio.create_task(self._restart_response_processing(websocket, user_id, connection))
                    else:
                        logger.info(f"User {user_id} no longer connected or task cancelled, not restarting response processing")
                        
                except Exception as e:
                    logger.error(f"Error in task callback for user {user_id}: {e}")
            
            task.add_done_callback(task_done_callback)
            logger.info(f"Started response processing task for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to start response processing for user {user_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to start response processing: {str(e)}"
            })
    
    async def _restart_response_processing(self, websocket: WebSocket, user_id: str, connection: Dict[str, Any]):
        """Restart response processing after failure"""
        try:
            logger.info(f"Attempting to restart response processing for user {user_id}")
            
            # Cancel existing task if any
            if "response_task" in connection and connection["response_task"]:
                connection["response_task"].cancel()
            
            # Check if Gemini session is still valid
            gemini_session = connection.get("gemini_session")
            if not gemini_session:
                logger.error(f"No valid Gemini session for restart for user {user_id}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Voice session lost. Please restart voice session."
                })
                return
            
            # Wait a brief moment before restart
            await asyncio.sleep(0.5)
            
            # Restart response processing
            await self._start_response_processing(websocket, user_id, connection)
            
            await websocket.send_json({
                "type": "voice_session_recovered",
                "message": "Voice session recovered"
            })
            
        except Exception as e:
            logger.error(f"Failed to restart response processing for user {user_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to recover voice session: {str(e)}"
            })
    
    async def _process_gemini_responses(self, websocket: WebSocket, user_id: str, connection: Dict[str, Any]):
        """Process responses from Gemini Live API with improved error handling"""
        gemini_session = None
        gemini_client = None
        
        try:
            gemini_session = connection["gemini_session"]
            gemini_client: GeminiLiveClient = connection["gemini_client"]
            
            if not gemini_session or not gemini_client:
                raise Exception("Invalid Gemini session or client")
            
            logger.info(f"Starting Gemini response processing for user {user_id}")
            
            async for response in gemini_client.process_responses(gemini_session, function_handler=connection["function_handler"].handle_function_call):
                # Check if connection is still active
                if user_id not in self.active_connections:
                    logger.info(f"Connection no longer active for user {user_id}, stopping response processing")
                    break
                
                response_type = response.get("type")
                logger.info(f"Received Gemini response type: {response_type} for user {user_id}")
                
                try:
                    if response_type == "audio":
                        # Stream audio response back to client
                        audio_data = response.get("audio_data")
                        if audio_data:
                            import base64
                            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
                            
                            await websocket.send_json({
                                "type": "audio_response",
                                "data": encoded_audio,
                                "format": "audio/pcm;rate=24000"
                            })
                    
                    elif response_type == "text":
                        # Send text response (for debugging)
                        await websocket.send_json({
                            "type": "text_response",
                            "text": response.get("text")
                        })
                    
                    elif response_type == "function_call":
                        # Function call was executed, send status
                        await websocket.send_json({
                            "type": "function_executed",
                            "function_name": response.get("function_call", {}).get("name"),
                            "message": "Gmail operation completed"
                        })
                    
                    # Update session state
                    session_state = self.session_manager.get_session_state(user_id)
                    if session_state:
                        await websocket.send_json({
                            "type": "session_state",
                            "current_index": session_state.get("current_index"),
                            "total_messages": session_state.get("total_messages"),
                            "has_more": session_state.get("next_page_token") is not None
                        })
                
                except Exception as response_error:
                    logger.error(f"Error processing individual response for user {user_id}: {response_error}")
                    # Continue processing other responses
                    continue
        
        except asyncio.CancelledError:
            logger.info(f"Response processing cancelled for user {user_id}")
            raise
        except Exception as e:
            logger.error(f"Gemini response processing error for user {user_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Try to notify the client about the error
            try:
                if user_id in self.active_connections:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Response processing error: {str(e)}"
                    })
            except:
                pass  # Ignore WebSocket send errors during cleanup
            
            # Re-raise the exception to trigger restart logic
            raise
        
        finally:
            logger.info(f"Response processing finished for user {user_id}")
    
    async def _end_voice_session(self, websocket: WebSocket, user_id: str, connection: Dict[str, Any]):
        """End the current voice session"""
        try:
            session_context = connection.get("session_context")
            gemini_session = connection.get("gemini_session")
            
            if session_context and gemini_session:
                # Properly close the context manager
                await session_context.__aexit__(None, None, None)
                connection["gemini_session"] = None
                connection["session_context"] = None
            
            await websocket.send_json({
                "type": "voice_session_ended",
                "message": "Voice session ended"
            })
            
            logger.info(f"Voice session ended for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error ending voice session for user {user_id}: {e}")
    
    async def disconnect(self, user_id: str):
        """Clean up connection"""
        try:
            if user_id in self.active_connections:
                connection = self.active_connections[user_id]
                
                # Cancel response processing task
                response_task = connection.get("response_task")
                if response_task and not response_task.done():
                    logger.info(f"Cancelling response processing task for user {user_id}")
                    response_task.cancel()
                    try:
                        await response_task
                    except asyncio.CancelledError:
                        pass  # Expected when cancelling
                    except Exception as e:
                        logger.error(f"Error while cancelling response task for user {user_id}: {e}")
                
                # Close Gemini session if active
                session_context = connection.get("session_context")
                gemini_session = connection.get("gemini_session")
                
                if session_context and gemini_session:
                    try:
                        await session_context.__aexit__(None, None, None)
                        logger.info(f"Closed Gemini session for user {user_id}")
                    except Exception as e:
                        logger.error(f"Error closing Gemini session for user {user_id}: {e}")
                
                # Remove from active connections
                del self.active_connections[user_id]
                
                logger.info(f"WebSocket disconnected for user {user_id}")
        
        except Exception as e:
            logger.error(f"Disconnect error for user {user_id}: {e}")
    
    def _create_gmail_service(self, credentials):
        """Create Gmail service with user credentials"""
    
        return GmailService(credentials)