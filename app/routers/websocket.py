"""
WebSocket handler for audio-only streaming (following auto-translator-server architecture)

Multi-user safe: All functions are stateless, state is stored per-session
"""
import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.services.gemini_service import GeminiLiveClient
from app.services.function_handler import GmailFunctionHandler
from app.services.gmail_service import GmailService
from app.services.session_service import SessionManager
from app.services.voice_session_manager import voice_session_manager, VoiceSession
from app.services.gmail_oauth_service import UserCredentialStore
from .websocket_helpers import safe_websocket_close, is_websocket_connected, send_bytes_safe


logger = logging.getLogger(__name__)

# Singleton services (stateless, safe for multi-user)
session_manager = SessionManager()
credential_store = UserCredentialStore()


async def handle_incoming_audio(
    websocket: WebSocket,
    session: VoiceSession
):
    """Handle incoming audio stream from client"""
    try:
        while session.active:
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info(f"WebSocket no longer connected (incoming), session {session.id}")
                break

            # Receive raw audio bytes
            audio_bytes = await websocket.receive_bytes()

            # Send to Gemini Live API if session is active
            gemini_session = session.gemini_session
            if gemini_session and session.gemini_client:
                gemini_client: GeminiLiveClient = session.gemini_client
                mime_type = "audio/pcm;rate=16000"
                await gemini_client.send_audio_chunk(gemini_session, audio_bytes, mime_type)
            else:
                logger.debug(f"No active Gemini session for {session.id}, buffering audio")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected (incoming), session {session.id}")
        raise
    except asyncio.CancelledError:
        logger.info(f"Incoming audio task cancelled, session {session.id}")
        raise
    except Exception as e:
        logger.error(f"Error handling incoming audio for session {session.id}: {e}")
        raise


async def handle_outgoing_audio(
    websocket: WebSocket,
    session: VoiceSession
):
    """Handle outgoing audio stream to client from Gemini responses"""
    try:
        # Wait for voice session to start via HTTP endpoint
        while session.active and not session.gemini_session:
            await asyncio.sleep(0.5)

        if not session.gemini_session or not session.gemini_client:
            logger.info(f"Session {session.id} closed before voice session started")
            return

        logger.info(f"Starting outgoing audio processing for session {session.id}")

        # Continuous loop like reference project - keeps task running after each turn completes
        while session.active:
            if not is_websocket_connected(websocket):
                logger.info(f"WebSocket no longer connected (outgoing), session {session.id}")
                break

            gemini_session = session.gemini_session
            gemini_client = session.gemini_client

            if not gemini_session or not gemini_client:
                logger.debug(f"Gemini session not ready, waiting...")
                await asyncio.sleep(0.5)
                continue

            # Process responses from Gemini Live API (processes one conversational turn)
            # This will complete when the turn ends (e.g., on interruption, end of response, etc.)
            async for response in gemini_client.process_responses(
                gemini_session,
                function_handler=session.function_handler.handle_function_call if session.function_handler else None
            ):
                # Check if session is still active
                if not session.active or not is_websocket_connected(websocket):
                    logger.info(f"Session no longer active, stopping outgoing audio for {session.id}")
                    break

                response_type = response.get("type")

                # Only send audio data over WebSocket - all other responses are internal
                if response_type == "audio":
                    audio_data = response.get("audio_data")
                    if audio_data and websocket.client_state == WebSocketState.CONNECTED:
                        await send_bytes_safe(websocket, audio_data)

                elif response_type == "interrupted":
                    # Gemini VAD detected interruption
                    # Client will naturally detect when audio stops coming
                    logger.info(f"Gemini VAD interruption detected for session {session.id}")

                elif response_type == "session_resumption_update":
                    # Handle session resumption updates
                    resumption_data = response.get("resumption_data", {})
                    if resumption_data.get("resumable") and resumption_data.get("new_handle"):
                        new_handle = resumption_data["new_handle"]
                        await session_manager.store_gemini_resumption_token(session.user_id, new_handle)
                        logger.info(f"Stored resumption handle for session {session.id}")

                elif response_type == "goaway":
                    # Handle GoAway messages
                    goaway_data = response.get("goaway_data", {})
                    logger.info(f"Received GoAway for session {session.id}: {goaway_data}")
                    if goaway_data.get("resumption_token"):
                        await session_manager.handle_gemini_goaway(session.user_id, goaway_data)

            # Turn completed, loop continues to wait for next turn
            logger.debug(f"Turn completed for session {session.id}, waiting for next turn")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected (outgoing), session {session.id}")
        raise
    except asyncio.CancelledError:
        logger.info(f"Outgoing audio task cancelled, session {session.id}")
        raise
    except Exception as e:
        logger.error(f"Error handling outgoing audio for session {session.id}: {e}")
        raise


async def start_voice_session(user_id: str, session: VoiceSession):
    """
    Initialize Gemini Live session for voice processing
    Called via HTTP endpoint POST /api/sessions/{session_id}/voice/start
    """
    try:
        if not session.function_handler:
            raise Exception("Gmail service not initialized - authorization required")

        gemini_client: GeminiLiveClient = session.gemini_client
        function_handler: GmailFunctionHandler = session.function_handler

        # Get Gemini Live session context manager
        session_context = await gemini_client.create_session(
            function_handler=function_handler.handle_function_call
        )

        # Start the session using async context manager
        gemini_session = await session_context.__aenter__()

        # Update session with Gemini Live session
        session.gemini_session = gemini_session
        session.session_context = session_context

        logger.info(f"Voice session started for user {user_id}, session {session.id}")

    except Exception as e:
        logger.error(f"Failed to start voice session for user {user_id}: {e}")
        raise


async def stop_voice_session(user_id: str, session: VoiceSession):
    """
    Stop Gemini Live session
    Called via HTTP endpoint POST /api/sessions/{session_id}/voice/stop
    """
    try:
        session_context = session.session_context
        gemini_session = session.gemini_session

        if session_context and gemini_session:
            # Properly close the context manager
            await session_context.__aexit__(None, None, None)
            session.gemini_session = None
            session.session_context = None

        logger.info(f"Voice session stopped for user {user_id}, session {session.id}")

    except Exception as e:
        logger.error(f"Error stopping voice session for user {user_id}: {e}")
        raise


def create_gmail_service(credentials, user_id: str) -> GmailService:
    """Create Gmail service with user credentials"""
    return GmailService(credentials, user_id)
