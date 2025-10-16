import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect

from app.services.gemini_service import GeminiLiveClient
from app.services.voice_session_manager import VoiceSession
from app.config import settings
from .websocket_helpers import is_websocket_connected


logger = logging.getLogger(__name__)


async def handle_incoming_audio(
    websocket: WebSocket,
    voice_session: VoiceSession
):
    """Handle incoming audio from client and forward to Gemini"""
    try:
        while voice_session.active:
            if not is_websocket_connected(websocket):
                logger.info(f"WebSocket no longer connected (incoming), session {voice_session.id}")
                break

            # Receive audio bytes directly
            audio_data = await websocket.receive_bytes()

            # Send to Gemini if session is active
            gemini_session = voice_session.gemini_session

            if gemini_session:
                from google.genai import types
                mime_type = f"{settings.AUDIO_FORMAT};rate={settings.AUDIO_SAMPLE_RATE}"
                try:
                    await gemini_session.send_realtime_input(
                        audio=types.Blob(
                            data=audio_data,
                            mime_type=mime_type
                        )
                    )
                except Exception as e:
                    logger.error(f"Error sending audio to Gemini for session {voice_session.id}: {e}")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected (incoming), session {voice_session.id}")
        raise
    except asyncio.CancelledError:
        logger.info(f"Incoming audio task cancelled, session {voice_session.id}")
        raise
    except Exception as e:
        logger.error(f"Error handling incoming audio for session {voice_session.id}: {e}")
        raise


async def handle_outgoing_audio(
    websocket: WebSocket,
    voice_session: VoiceSession
):
    """Handle outgoing audio from Gemini message queue to client (following auto-translator pattern)"""
    try:
        while voice_session.active:
            try:
                # Wait for audio data from queue with timeout
                audio_data = await asyncio.wait_for(
                    voice_session.message_queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                if not voice_session.active:
                    logger.debug(f"Outgoing audio queue timeout, session {voice_session.id} is inactive.")
                    break
                continue

            if audio_data:
                if not is_websocket_connected(websocket):
                    logger.info(f"WebSocket no longer connected (outgoing), session {voice_session.id}")
                    break
                # Send raw bytes directly (like auto-translator)
                await websocket.send_bytes(audio_data)
            else:
                logger.warning(f"Received empty/None audio data from queue, session {voice_session.id}")

            voice_session.message_queue.task_done()

    except WebSocketDisconnect:
        logger.info(f"Client disconnected (outgoing), session {voice_session.id}")
        raise
    except asyncio.CancelledError:
        logger.info(f"Outgoing audio task cancelled, session {voice_session.id}")
        raise
    except Exception as e:
        logger.error(f"Error handling outgoing audio for session {voice_session.id}: {e}")
        raise
