import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from starlette.websockets import WebSocketState

from app.services.gemini_service import GeminiLiveClient
from app.services.function_handler import GmailFunctionHandler
from app.services.retry_handler import ConnectionRetryHandler, RetryHandler
from app.services.gmail_service import GmailService
from app.services.session_service import SessionManager
from app.services.voice_session_manager import voice_session_manager
from app.services.gmail_oauth_service import UserCredentialStore
from .websocket_helpers import safe_websocket_close, is_websocket_connected, send_json_safe


logger = logging.getLogger(__name__)


class VoiceWebSocketHandler:
    """Handle WebSocket connections for streaming voice processing with session management"""

    def __init__(self):
        self.session_manager = SessionManager()
        self.credential_store = UserCredentialStore()
        self.retry_handler = ConnectionRetryHandler(max_attempts=3)
    
    async def connect(self, websocket: WebSocket, firebase_user_id: str, session_id: str):
        """Establish WebSocket connection for pre-authenticated Firebase user with session validation"""
        try:
            user_id = firebase_user_id

            if not user_id:
                await safe_websocket_close(websocket, code=4001, reason="Invalid user ID")
                return None

            # Validate voice session exists and is active
            voice_session = await voice_session_manager.get_session(session_id)
            if not voice_session or not voice_session.active:
                await safe_websocket_close(websocket, code=4003, reason="Invalid or expired session")
                logger.warning(f"WebSocket connection attempt with invalid session: {session_id}")
                return None

            # Validate session ownership
            if voice_session.user_id != user_id:
                await safe_websocket_close(websocket, code=4004, reason="Unauthorized session access")
                logger.warning(f"User {user_id} attempted to access session {session_id} owned by {voice_session.user_id}")
                return None

            # Accept WebSocket connection
            await websocket.accept()
            logger.info(f"WebSocket accepted for user {user_id}, session {session_id}")

            # Get user's Gmail credentials from Redis
            gmail_credentials = await self.credential_store.get_credentials(user_id)
            if not gmail_credentials:
                # Send error message with auth URL before closing
                logger.info(f"Gmail auth not found for user {user_id}")
                await send_json_safe(websocket, {
                    "type": "error",
                    "message": "Gmail authorization required. Please authorize Gmail access first.",
                    "action_required": "gmail_auth",
                    "auth_url": f"/api/auth/gmail/authorize",
                    "user_id": user_id
                })
                await safe_websocket_close(websocket, code=4002, reason="Gmail authorization required")
                return None

            # Initialize services for this user
            gmail_service = self._create_gmail_service(gmail_credentials, user_id)
            function_handler = GmailFunctionHandler(gmail_service, self.session_manager, user_id)

            # Initialize Gemini Live client
            gemini_client = GeminiLiveClient()

            # Store services in voice session object
            voice_session.websocket = websocket
            voice_session.gmail_service = gmail_service
            voice_session.function_handler = function_handler
            voice_session.gemini_client = gemini_client

            # Send connection success
            await send_json_safe(websocket, {
                "type": "connected",
                "message": "Voice assistant ready",
                "user_id": user_id,
                "session_id": session_id
            })

            logger.info(f"WebSocket connected for user {user_id}, session {session_id}")
            return user_id

        except Exception as e:
            logger.error(f"Connection error: {e}")
            await safe_websocket_close(websocket, code=4000, reason="Connection failed")
            return None
    
    async def handle_message(self, websocket: WebSocket, user_id: str, session_id: str, message: Dict[str, Any]):
        """Process incoming WebSocket message"""
        try:
            message_type = message.get("type")
            voice_session = voice_session_manager.get_cached_session(session_id)

            if not voice_session:
                await send_json_safe(websocket, {
                    "type": "error",
                    "message": "Session not found"
                })
                return

            if message_type == "start_voice_session":
                await self._start_voice_session(websocket, user_id, voice_session)

            elif message_type == "audio_chunk":
                await self._process_audio_chunk(websocket, user_id, voice_session, message)

            elif message_type == "end_voice_session":
                await self._end_voice_session(websocket, user_id, voice_session)

            else:
                await send_json_safe(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

        except Exception as e:
            logger.error(f"Message handling error for user {user_id}: {e}")
            await send_json_safe(websocket, {
                "type": "error",
                "message": f"Error processing message: {str(e)}"
            })
    
    async def _start_voice_session(self, websocket: WebSocket, user_id: str, voice_session):
        """Start a new Gemini Live voice session"""
        try:
            gemini_client: GeminiLiveClient = voice_session.gemini_client
            function_handler: GmailFunctionHandler = voice_session.function_handler

            # Get Gemini Live session context manager
            session_context = await gemini_client.create_session(
                function_handler=function_handler.handle_function_call
            )

            # Start the session using async context manager
            gemini_session = await session_context.__aenter__()

            voice_session.gemini_session = gemini_session
            voice_session.session_context = session_context  # Store context for cleanup
            voice_session.response_task = None  # Track response processing task

            # Start processing responses from Gemini with error handling
            await self._start_response_processing(websocket, user_id, voice_session)

            await send_json_safe(websocket, {
                "type": "voice_session_started",
                "message": "Ready to receive audio"
            })

            logger.info(f"Voice session started for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to start voice session for user {user_id}: {e}")
            await send_json_safe(websocket, {
                "type": "error",
                "message": f"Failed to start voice session: {str(e)}"
            })
    
    async def _process_audio_chunk(self, websocket: WebSocket, user_id: str,
                                 voice_session, message: Dict[str, Any]):
        """Process audio chunk from client"""
        try:
            gemini_session = voice_session.gemini_session
            if not gemini_session:
                await send_json_safe(websocket, {
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
            gemini_client: GeminiLiveClient = voice_session.gemini_client
            await gemini_client.send_audio_chunk(gemini_session, audio_bytes, mime_type)

        except Exception as e:
            logger.error(f"Audio processing error for user {user_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Audio processing error: {str(e)}"
            })
    
    async def _start_response_processing(self, websocket: WebSocket, user_id: str, voice_session):
        """Start continuous response processing with monitoring"""
        try:
            # Start the continuous monitor (only create once per session)
            if not voice_session.response_monitor_active:
                voice_session.response_monitor_active = True
                asyncio.create_task(self._continuous_response_monitor(websocket, user_id, voice_session))
                logger.info(f"Started continuous response monitoring for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to start response processing for user {user_id}: {e}")
            await send_json_safe(websocket, {
                "type": "error",
                "message": f"Failed to start response processing: {str(e)}"
            })
    
    async def _continuous_response_monitor(self, websocket: WebSocket, user_id: str, voice_session):
        """Continuously monitor and restart response processing tasks"""
        logger.info(f"Starting continuous response monitoring for user {user_id}")

        while voice_session.active and is_websocket_connected(websocket):
            try:
                # Create new processing task
                task = asyncio.create_task(self._process_gemini_responses(websocket, user_id, voice_session))
                voice_session.response_task = task
                logger.debug(f"Created new response processing task for user {user_id}")

                # Wait for it to complete
                await task
                logger.info(f"Response processing completed normally for user {user_id} - creating new task")

                # Loop will automatically create a new task

            except asyncio.CancelledError:
                logger.info(f"Response processing monitoring cancelled for user {user_id}")
                break

            except Exception as e:
                if not voice_session.active:
                    logger.info(f"Session {voice_session.id} no longer active, stopping monitor")
                    break

                logger.error(f"Response processing failed for user {user_id}: {e}")

                # Handle retry logic
                retry_count = self.retry_handler.get_retry_count(user_id, "response_processing")

                if RetryHandler.is_retryable_error(e) and retry_count < 3:
                    logger.info(f"Retrying response processing for user {user_id} ({retry_count + 1}/3)")
                    try:
                        # Restart session with resumption
                        await self._restart_session_for_user(websocket, user_id, voice_session)
                        # Continue loop to create new processing task
                    except Exception as restart_error:
                        logger.error(f"Failed to restart session for user {user_id}: {restart_error}")
                        await send_json_safe(websocket, {
                            "type": "error",
                            "message": f"Failed to restart voice session: {str(restart_error)}"
                        })
                        break
                else:
                    logger.error(f"Max retries exceeded for user {user_id}: {e}")
                    self.retry_handler.reset_retry_count(user_id, "response_processing")
                    await send_json_safe(websocket, {
                        "type": "error",
                        "message": f"Voice session failed after maximum retries: {str(e)}"
                    })
                    break

        # Cleanup
        voice_session.response_monitor_active = False
        logger.info(f"Stopped continuous response monitoring for user {user_id}")
    
    async def _restart_session_for_user(self, websocket: WebSocket, user_id: str, voice_session):
        """Restart Gemini session for user (used by continuous monitor)"""

        async def attempt_restart():
            logger.info(f"Attempting to restart response processing for user {user_id}")

            # Cancel existing task if any
            if voice_session.response_task:
                voice_session.response_task.cancel()

            # Try to resume session using stored resumption token
            resumption_handle = await self.session_manager.get_gemini_resumption_token(user_id)

            # Create new Gemini session (with resumption if available)
            gemini_client = GeminiLiveClient()
            gemini_session_context = await gemini_client.create_session(
                function_handler=voice_session.function_handler.handle_function_call,
                resumption_handle=resumption_handle
            )

            # Update voice session with new Gemini session
            voice_session.gemini_client = gemini_client
            voice_session.session_context = gemini_session_context
            voice_session.gemini_session = await gemini_session_context.__aenter__()

            # Start new response processing task
            await self._start_response_processing(websocket, user_id, voice_session)

            return True

        try:
            # Use retry handler for restart attempts
            await self.retry_handler.execute_connection_with_retry(
                user_id=user_id,
                async_func=attempt_restart,
                context_name="response_processing"
            )

            await send_json_safe(websocket, {
                "type": "voice_session_recovered",
                "message": "Voice session recovered"
            })

        except Exception as e:
            logger.error(f"Failed to restart response processing for user {user_id} after all retries: {e}")
            # Clear retry counter on permanent failure
            self.retry_handler.reset_retry_count(user_id, "response_processing")
            await send_json_safe(websocket, {
                "type": "error",
                "message": f"Failed to recover voice session after maximum retries: {str(e)}"
            })
    
    async def _process_gemini_responses(self, websocket: WebSocket, user_id: str, voice_session):
        """Process responses from Gemini Live API with improved error handling"""
        gemini_session = None
        gemini_client = None

        try:
            gemini_session = voice_session.gemini_session
            gemini_client: GeminiLiveClient = voice_session.gemini_client

            if not gemini_session or not gemini_client:
                raise Exception("Invalid Gemini session or client")

            logger.info(f"Starting Gemini response processing for user {user_id}")

            async for response in gemini_client.process_responses(gemini_session, function_handler=voice_session.function_handler.handle_function_call):
                # Check if session is still active
                if not voice_session.active or not is_websocket_connected(websocket):
                    logger.info(f"Session no longer active for user {user_id}, stopping response processing")
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

                            await send_json_safe(websocket, {
                                "type": "audio_response",
                                "data": encoded_audio,
                                "format": "audio/pcm;rate=24000"
                            })

                    elif response_type == "text":
                        # Send text response (for debugging)
                        await send_json_safe(websocket, {
                            "type": "text_response",
                            "text": response.get("text")
                        })

                    elif response_type == "function_call":
                        # Function call was executed, send status
                        await send_json_safe(websocket, {
                            "type": "function_executed",
                            "function_name": response.get("function_call", {}).get("name"),
                            "message": "Gmail operation completed"
                        })

                    elif response_type == "session_resumption_update":
                        # Handle session resumption updates from Gemini
                        resumption_data = response.get("resumption_data", {})
                        if resumption_data.get("resumable") and resumption_data.get("new_handle"):
                            # Store the new resumption handle for future use
                            new_handle = resumption_data["new_handle"]
                            success = await self.session_manager.store_gemini_resumption_token(user_id, new_handle)
                            logger.info(f"Stored new resumption handle for user {user_id}: {success}")
                        else:
                            logger.debug(f"Session not resumable for user {user_id}")

                    elif response_type == "goaway":
                        # Handle GoAway messages (though session resumption should handle this)
                        goaway_data = response.get("goaway_data", {})
                        logger.info(f"Received GoAway message for user {user_id}: {goaway_data}")
                        if goaway_data.get("resumption_token"):
                            await self.session_manager.handle_gemini_goaway(user_id, goaway_data)

                    # Update session state
                    session_state = await self.session_manager.get_session_state(user_id)
                    if session_state:
                        await send_json_safe(websocket, {
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
                if voice_session.active and is_websocket_connected(websocket):
                    await send_json_safe(websocket, {
                        "type": "error",
                        "message": f"Response processing error: {str(e)}"
                    })
            except:
                pass  # Ignore WebSocket send errors during cleanup
            
            # Re-raise the exception to trigger restart logic
            raise
        
        finally:
            logger.info(f"Response processing finished for user {user_id}")
    
    async def _end_voice_session(self, websocket: WebSocket, user_id: str, voice_session):
        """End the current voice session"""
        try:
            session_context = voice_session.session_context
            gemini_session = voice_session.gemini_session

            if session_context and gemini_session:
                # Properly close the context manager
                await session_context.__aexit__(None, None, None)
                voice_session.gemini_session = None
                voice_session.session_context = None

            await send_json_safe(websocket, {
                "type": "voice_session_ended",
                "message": "Voice session ended"
            })

            logger.info(f"Voice session ended for user {user_id}")

        except Exception as e:
            logger.error(f"Error ending voice session for user {user_id}: {e}")
    
    async def disconnect(self, session_id: str):
        """Clean up voice session (now handled in controller, kept for compatibility)"""
        try:
            voice_session = voice_session_manager.get_cached_session(session_id)
            if not voice_session:
                return

            # Cancel response processing task
            response_task = voice_session.response_task
            if response_task and not response_task.done():
                logger.info(f"Cancelling response processing task for session {session_id}")
                response_task.cancel()
                try:
                    await response_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
                except Exception as e:
                    logger.error(f"Error while cancelling response task for session {session_id}: {e}")

            # Close Gemini session if active
            session_context = voice_session.session_context
            gemini_session = voice_session.gemini_session

            if session_context and gemini_session:
                try:
                    await session_context.__aexit__(None, None, None)
                    logger.info(f"Closed Gemini session for session {session_id}")
                except Exception as e:
                    logger.error(f"Error closing Gemini session for session {session_id}: {e}")

            # Clean up retry counters
            self.retry_handler.cleanup_user_retries(voice_session.user_id)

            # Mark session as inactive
            voice_session.active = False
            await voice_session_manager.update_session(voice_session)

            logger.info(f"Session {session_id} cleanup complete")

        except Exception as e:
            logger.error(f"Disconnect error for user {user_id}: {e}")
    
    def _create_gmail_service(self, credentials, user_id: str):
        """Create Gmail service with user credentials and user ID"""
        return GmailService(credentials, user_id)