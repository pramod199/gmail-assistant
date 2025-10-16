import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from google import genai
from google.genai import types

from app.config import settings


logger = logging.getLogger(__name__)


class GeminiLiveClient:
    """Gemini Live API client for streaming voice processing"""

    def __init__(self):
        # Get API key from settings
        api_key = settings.GEMINI_API_KEY

        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError(
                "Gemini API key is required. Please set the settings.GEMINI_API_KEY environment variable. "
                "You can get an API key from https://makersuite.google.com/app/apikey"
            )

        logger.info("Initializing Gemini Live client with API key from settings")
        # Configure client with timeout from settings
        # With context window compression enabled, sessions can run indefinitely
        # Default 5 minutes allows for natural conversation flow with pauses
        timeout_ms = settings.GEMINI_HTTP_TIMEOUT
        logger.info(f"Setting Gemini HTTP timeout to {timeout_ms}ms ({timeout_ms/60000:.1f} minutes)")
        http_options = genai.types.HttpOptions(timeout=timeout_ms)
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = "gemini-2.5-flash-live-preview"

        # Background task management (following auto-translator pattern)
        self.active_sessions: Dict[str, asyncio.Task] = {}  # Track background session tasks
        self.session_resumption_handles: Dict[str, str] = {}  # Store resumption handles for reconnection
        
        # Function definitions for Gmail operations
        self.functions = [
            {
                "name": "read_messages",
                "description": "Fetch and read Gmail messages using Gmail search queries",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gmail_query": {
                            "type": "string",
                            "description": "Gmail search query (e.g., 'is:unread', 'from:john@example.com', 'is:important from:boss', 'has:attachment', 'subject:meeting'). Defaults to 'is:unread' if not provided."
                        },
                        "message_index": {
                            "type": "integer",
                            "description": "Specific message index to read (0-based)"
                        },
                        "read_full": {
                            "type": "boolean",
                            "description": "Whether to read full message or just preview"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of messages to fetch (default: 10)"
                        }
                    }
                }
            },
            {
                "name": "navigate_messages",
                "description": "Navigate through message list",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["next", "previous", "first", "last"],
                            "description": "Navigation direction"
                        },
                        "search_criteria": {
                            "type": "object",
                            "description": "Search criteria for finding specific messages",
                            "properties": {
                                "sender": {"type": "string"},
                                "subject_contains": {"type": "string"},
                                "date_range": {"type": "string"}
                            }
                        }
                    }
                }
            },
            {
                "name": "summarize_message",
                "description": "Summarize the current or specified message",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_index": {
                            "type": "integer",
                            "description": "Message index to summarize (optional, defaults to current)"
                        }
                    }
                }
            },
            {
                "name": "mark_message",
                "description": "Change message status",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["read", "unread", "star", "unstar", "archive", "delete"],
                            "description": "Action to perform on message"
                        },
                        "message_index": {
                            "type": "integer",
                            "description": "Message index to act on (optional, defaults to current)"
                        }
                    }
                }
            },
            {
                "name": "draft_email",
                "description": "Create or manage email draft",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create", "edit", "send", "cancel"],
                            "description": "Draft action to perform"
                        },
                        "recipient": {
                            "type": "string", 
                            "description": "Email recipient (required for new drafts, optional for replies)"
                        },
                        "subject": {
                            "type": "string", 
                            "description": "Email subject (required for new drafts, optional for replies)" 
                        },
                        "content": {"type": "string", "description": "Email body content (always required)"},
                        "reply_to": {
                            "type": "boolean", 
                            "description": "True if replying to current message, False for new draft. Use true for commands like 'reply to this message', 'respond to this email', 'write back'. Use false for 'create new email', 'send email to someone'."
                        },
                    }
                }
            }
        ]
    
    def get_session_config(self) -> types.LiveConnectConfig:
        """Get configuration for Gemini Live session with context compression and session resumption.

        Note: Interruption (barge-in) works automatically in Gemini Live API by default.
        No explicit realtime_input_config needed - when user starts speaking, Gemini naturally stops.
        """
        # Configure speech settings with voice (following auto-translator pattern)
        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.GEMINI_VOICE)
            )
        )

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],

            # Set media resolution to MEDIUM for better real-time performance (following auto-translator pattern)
            media_resolution="MEDIA_RESOLUTION_MEDIUM",

            # Configure voice for natural conversation (following auto-translator pattern)
            speech_config=speech_config,

            # Enable context window compression with sliding window
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),

            # Always enable session resumption (handle will be set during session creation)
            session_resumption=types.SessionResumptionConfig(),

            # System instruction for Gmail assistant behavior
            system_instruction=types.Content(
                parts=[types.Part(
                    text="""You are a helpful Gmail voice assistant. You can:
            
1. Read emails aloud - When users ask to read messages, immediately fetch and read the first one
2. Navigate through messages using next/previous commands
3. Summarize emails with key points and action items
4. Mark messages as read, starred, etc.
5. Create and manage email drafts
6. Search for specific messages by sender or topic

IMPORTANT NAVIGATION RULES:
- ALWAYS use the navigate_messages() function for ANY navigation request including:
  * "next message", "previous message", "go to next", "go to previous" 
  * "read my next message", "read my last message", "read the previous message"
  * "first message", "last message"
- For "read next/previous/first/last message" commands, prioritize navigate_messages() over read_messages()
- NEVER assume there are no more messages - let the navigate_messages() function check the session state and pagination tokens
- The navigate_messages() function will automatically fetch more messages if available using pagination
- Do not give responses like "no more messages" or "you've reached the end" without calling navigate_messages() first

Always provide natural, conversational responses. When reading emails, format content for voice delivery (convert timestamps to natural language, break long emails into digestible chunks).

For "read my messages" commands:
1. Fetch the messages
2. Immediately read the first message aloud
3. Let user know navigation options ("say next message to continue")

For navigation commands ("next", "previous", etc.):
1. ALWAYS call navigate_messages() function
2. Let the function handle pagination and message availability
3. Read the response from the function

For draft/email commands:
- Use reply_to=true for: "reply to this message", "respond to this email", "write back to them", "reply that..."
- Use reply_to=false for: "create new email", "send email to [person]", "draft an email to..."
- When reply_to=true, only provide content parameter - recipient and subject will be auto-populated from current message
- When reply_to=false, all parameters (recipient, subject, content) are required

Keep responses concise but informative. Ask for clarification when needed."""
                )]
            ),
            
            # Function calling tools
            tools=[types.Tool(function_declarations=self.functions)]
        )
    
    async def initialize_session(self, voice_session, function_handler: Callable = None) -> bool:
        """Initialize Gemini Live session in background task (following auto-translator pattern).

        This method starts a background task that manages the Gemini session lifecycle,
        including automatic reconnection and session resumption.

        Args:
            voice_session: VoiceSession object to initialize
            function_handler: Function to handle Gmail operations

        Returns:
            True if session initialized successfully, False otherwise
        """
        try:
            # Clear the event in case of re-initialization
            voice_session.initialization_event.clear()

            # Start background task to manage Gemini session
            task = asyncio.create_task(self._manage_gemini_session(voice_session, function_handler))
            self.active_sessions[voice_session.id] = task

            # Wait for Gemini session to be fully initialized
            await voice_session.initialization_event.wait()

            # Check if initialization was successful
            if not voice_session.gemini_session:
                logger.error(f"Gemini session not set after initialization for voice session {voice_session.id}")
                # Clean up failed task
                if voice_session.id in self.active_sessions:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            logger.debug(f"Early-failed task for session {voice_session.id} cancelled")
                    del self.active_sessions[voice_session.id]
                return False

            return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for Gemini session {voice_session.id} to initialize")
            return False
        except Exception as e:
            logger.error(f"Error initializing Gemini session {voice_session.id}: {e}")
            return False

    async def _manage_gemini_session(self, voice_session, function_handler: Callable = None):
        """Background task to manage Gemini session with automatic reconnection.

        This runs independently of WebSocket lifecycle, allowing session persistence
        across WebSocket disconnections.

        Based on auto-translator pattern with:
        - Automatic reconnection with exponential backoff
        - Session resumption using stored handles
        - Turn-based response processing
        """
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second
        consecutive_errors = 0

        while voice_session.active and consecutive_errors < max_retries:
            gemini_api_session = None
            try:
                config = self.get_session_config()

                # Attempt session resumption if handle available
                resumption_handle = self.session_resumption_handles.get(voice_session.id)
                if resumption_handle:
                    logger.info(f"Attempting to resume session {voice_session.id} with handle")
                    config.session_resumption.handle = resumption_handle

                async with self.client.aio.live.connect(model=self.model, config=config) as gemini_api_session_ctx:
                    # Store session and signal initialization
                    voice_session.gemini_session = gemini_api_session_ctx
                    gemini_api_session = gemini_api_session_ctx

                    # Only set initialization event on first successful connection
                    if consecutive_errors == 0:
                        voice_session.initialization_event.set()

                    consecutive_errors = 0  # Reset error counter on success
                    logger.info(f"Session {voice_session.id} {'reconnected' if resumption_handle else 'initialized'}")

                    # Process responses in turn-based loop
                    while voice_session.active:
                        try:
                            turn = gemini_api_session_ctx.receive()
                            async for response in turn:
                                if not voice_session.active:
                                    break

                                # Handle session resumption updates
                                if hasattr(response, 'session_resumption_update') and response.session_resumption_update:
                                    update = response.session_resumption_update
                                    if update.resumable and update.new_handle:
                                        self.session_resumption_handles[voice_session.id] = update.new_handle
                                        logger.info(f"Stored session resumption handle for {voice_session.id}")

                                # Handle go_away (session expiring soon)
                                if hasattr(response, 'go_away') and response.go_away:
                                    logger.warning(f"Session {voice_session.id} will terminate in {response.go_away.time_left} seconds")
                                    break  # Trigger reconnection

                                # Handle audio response (following auto-translator pattern)
                                if response.data is not None:
                                    try:
                                        await voice_session.message_queue.put(response.data)
                                    except asyncio.QueueFull:
                                        logger.warning(f"Queue full for session {voice_session.id}, dropping audio")

                                # Handle function calls
                                if hasattr(response, 'tool_call') and response.tool_call:
                                    for function_call in response.tool_call.function_calls:
                                        if function_handler:
                                            try:
                                                function_result = await function_handler({
                                                    "name": function_call.name,
                                                    "parameters": function_call.args,
                                                    "id": function_call.id
                                                })

                                                if not isinstance(function_result, dict):
                                                    function_result = {"result": str(function_result)}

                                                # Send result back to Gemini
                                                await gemini_api_session_ctx.send_tool_response(
                                                    function_responses=[types.FunctionResponse(
                                                        id=function_call.id,
                                                        name=function_call.name,
                                                        response=function_result
                                                    )]
                                                )
                                            except Exception as e:
                                                logger.error(f"Function execution error: {e}")

                                # Handle user interruption (barge-in)
                                if hasattr(response, 'server_content') and response.server_content:
                                    if hasattr(response.server_content, 'interrupted') and response.server_content.interrupted:
                                        logger.info(f"User interrupted generation for session {voice_session.id}")

                                        # Clear audio queue immediately to stop playback
                                        while not voice_session.message_queue.empty():
                                            try:
                                                voice_session.message_queue.get_nowait()
                                                voice_session.message_queue.task_done()
                                            except asyncio.QueueEmpty:
                                                break
                                        logger.info(f"Cleared audio queue due to interruption")

                                        # Send interruption signal to client to clear its queue
                                        if voice_session.websocket:
                                            try:
                                                import json
                                                await voice_session.websocket.send_text(json.dumps({
                                                    "type": "interruption",
                                                    "message": "User interrupted"
                                                }))
                                                logger.info(f"Sent interruption signal to client for session {voice_session.id}")
                                            except Exception as e:
                                                logger.error(f"Failed to send interruption signal: {e}")

                                # Keep the tool_call_cancellation handler for function call cancellations
                                if hasattr(response, 'tool_call_cancellation') and response.tool_call_cancellation:
                                    cancelled_ids = response.tool_call_cancellation.ids
                                    logger.info(f"Tool calls cancelled: {cancelled_ids}")

                            if not voice_session.active:
                                break

                        except asyncio.CancelledError:
                            logger.info(f"Gemini session task for {voice_session.id} cancelled during receive loop")
                            raise
                        except Exception as e:
                            logger.error(f"Error in receive loop for {voice_session.id}: {e}")
                            if not voice_session.active:
                                break
                            break  # Trigger reconnection

                # Connection closed - attempt reconnection if session still active
                if voice_session.active:
                    logger.warning(f"Gemini connection closed for {voice_session.id}, attempting reconnection")
                    voice_session.gemini_session = None
                    consecutive_errors += 1
                    continue
                else:
                    logger.info(f"Session {voice_session.id} ended normally")
                    break

            except asyncio.CancelledError:
                logger.info(f"Gemini session management task cancelled for {voice_session.id}")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error managing Gemini session {voice_session.id} (attempt {consecutive_errors}/{max_retries}): {e}")

                # Signal initialization failure if event not yet set
                if consecutive_errors == 1 and not voice_session.initialization_event.is_set():
                    voice_session.initialization_event.set()

                if consecutive_errors < max_retries and voice_session.active:
                    logger.info(f"Retrying connection for {voice_session.id} in {retry_delay}s")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
                else:
                    logger.error(f"Max retries reached for {voice_session.id}")
                    break

        # Cleanup
        logger.debug(f"Cleaning up _manage_gemini_session for {voice_session.id}")
        voice_session.gemini_session = None
        voice_session.active = False

        # Signal initialization event if not already set
        if not voice_session.initialization_event.is_set():
            voice_session.initialization_event.set()

        # Remove from active sessions
        if voice_session.id in self.active_sessions:
            del self.active_sessions[voice_session.id]

        # Clear resumption handle
        self.session_resumption_handles.pop(voice_session.id, None)

        logger.info(f"Gemini session {voice_session.id} management task cleaned up")

    async def close_session(self, voice_session) -> None:
        """Close Gemini session and cancel background task.

        Args:
            voice_session: VoiceSession to close
        """
        logger.info(f"Closing Gemini session {voice_session.id}")
        voice_session.active = False

        # Clean up management task
        task = self.active_sessions.pop(voice_session.id, None)
        if task and not task.done():
            logger.info(f"Cancelling Gemini management task for {voice_session.id}")
            task.cancel()
            try:
                await task
                logger.info(f"Task for {voice_session.id} cancelled successfully")
            except asyncio.CancelledError:
                logger.info(f"Task for {voice_session.id} confirmed cancelled")
            except Exception as e:
                logger.error(f"Error cancelling task for {voice_session.id}: {e}")
        elif task and task.done():
            logger.info(f"Task for {voice_session.id} was already done")

        # Ensure initialization event is set
        if hasattr(voice_session, 'initialization_event') and not voice_session.initialization_event.is_set():
            voice_session.initialization_event.set()

        logger.info(f"Session {voice_session.id} closed successfully")

    async def send_text_input(self, session, text: str):
        """Send text input to session (for debugging)"""
        await session.send_message(types.LiveClientMessage(
            client_content=types.LiveClientContent(
                turns=[
                    types.Turn(
                        role="user",
                        parts=[types.Part(text=text)]
                    )
                ]
            )
        ))
    
    def format_voice_response(self, text: str) -> str:
        """Format text for natural voice delivery"""
        
        # Convert timestamps to natural language
        # This is a simplified version - you might want more sophisticated parsing
        formatted = text
        
        # Remove excessive whitespace
        formatted = re.sub(r'\s+', ' ', formatted)
        
        # Add natural pauses for better voice delivery
        formatted = formatted.replace('\n', ' ... ')
        formatted = formatted.replace('. ', '. ')
        
        return formatted.strip()