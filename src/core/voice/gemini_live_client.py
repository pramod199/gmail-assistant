import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from google import genai
from google.genai import types

from ...config.settings import GEMINI_API_KEY


logger = logging.getLogger(__name__)


class GeminiLiveClient:
    """Gemini Live API client for streaming voice processing"""
    
    def __init__(self):
        # Get API key from settings
        api_key = GEMINI_API_KEY
            
        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError(
                "Gemini API key is required. Please set the GEMINI_API_KEY environment variable. "
                "You can get an API key from https://makersuite.google.com/app/apikey"
            )
        
        logger.info("Initializing Gemini Live client with API key from settings")
        # Configure client with extended timeout for tool calling (2 minutes)
        http_options = genai.types.HttpOptions(timeout=60000)  # 120000 milliseconds = 2 minutes, 60000ms - 1 min
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = "gemini-2.5-flash-live-preview"
        
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
                            "enum": ["create", "edit", "save_to_gmail", "send", "cancel"],
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
        """Get configuration for Gemini Live session with context compression and session resumption"""
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            
            # Enable context window compression with sliding window
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            
            # Always enable session resumption (handle will be set during session creation)
            session_resumption=types.SessionResumptionConfig(),
            
            # Realtime input configuration with improved VAD for better speech recognition
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,                                          # Enable VAD
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,  # Detect speech start quickly
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,         # Wait longer for silence (KEY!)
                    silence_duration_ms=1200,                               # Wait 1.2s of silence before processing (CRITICAL!)
                    prefix_padding_ms=300                                    # Include 300ms before speech starts
                )
            ),
            
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
    
    async def create_session(self, function_handler: Callable = None, resumption_handle: str = None):
        """Create streaming session with function calling and resumption support"""
        config = self.get_session_config()
        
        # Set resumption handle if provided
        if resumption_handle:
            logger.info(f"Creating session with resumption handle")
            config.session_resumption.handle = resumption_handle
        else:
            logger.info(f"Creating new session without resumption")
        
        # Return the async context manager directly
        session_context = self.client.aio.live.connect(
            model=self.model,
            config=config
        )
        
        # Store function handler reference for later use
        session_context._function_handler = function_handler
        
        return session_context
    
    async def send_audio_chunk(self, session, audio_data: bytes, mime_type: str = "audio/pcm;rate=16000"):
        """Send audio chunk to Gemini Live API"""
        try:
            # Try the old method first
            await session.send_realtime_input(
                audio=types.Blob(
                    data=audio_data,
                    mime_type=mime_type
                )
            )
        except Exception as e:
            logger.error(f"Audio send error: {e}")
            # Just continue - audio sending failure shouldn't crash everything
    
    async def process_responses(self, session, function_handler: Callable = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Process responses from Gemini Live API and handle function calls"""
        logger.info(f"Starting Gemini Live response processing")
        logger.debug(f"Session type: {type(session)}")
        logger.debug(f"Session methods: {[method for method in dir(session) if not method.startswith('_')]}")
        
        try:
            response_count = 0
            async for response in session.receive():
                response_count += 1
                logger.debug(f"Processing response #{response_count}")
                logger.debug(f"Raw Gemini response: {response}")
                
                response_data = {
                    "type": "response",
                    "data": None,
                    "text": None,
                    "function_call": None,
                    "audio_data": None
                }
                
                # Handle audio response from server_content
                if hasattr(response, 'server_content') and response.server_content:
                    server_content = response.server_content
                    
                    # Check for audio data
                    if hasattr(server_content, 'model_turn') and server_content.model_turn:
                        model_turn = server_content.model_turn
                        for part in model_turn.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                logger.debug(f"Found audio data")
                                response_data["type"] = "audio"
                                response_data["audio_data"] = part.inline_data.data
                                yield response_data
                
                # Handle text response
                if hasattr(response, 'text') and response.text:
                    logger.debug(f"Found text response: {response.text}")
                    response_data["type"] = "text"
                    response_data["text"] = response.text
                    yield response_data
                
                # Handle tool calls (new format)
                if hasattr(response, 'tool_call') and response.tool_call:
                    logger.debug(f"Found tool call: {response.tool_call}")
                    
                    # Process each function call
                    for function_call in response.tool_call.function_calls:
                        logger.debug(f"Processing function: {function_call.name} with args: {function_call.args}")
                        
                        response_data["type"] = "function_call"
                        response_data["function_call"] = {
                            "name": function_call.name,
                            "parameters": function_call.args,
                            "id": function_call.id
                        }
                        
                        # Execute function if handler provided
                        if function_handler:
                            try:
                                logger.debug(f"Executing function with handler")
                                function_result = await function_handler(response_data["function_call"])
                                logger.debug(f"Function result: {function_result}")
                                logger.debug(f"Function result type: {type(function_result)}")
                                
                                # Ensure function result is a dict
                                if not isinstance(function_result, dict):
                                    function_result = {"result": str(function_result)}
                                
                                # Send function result back to Gemini using send_tool_response
                                logger.debug(f"Attempting to send function response...")
                                try:
                                    function_responses = [
                                        types.FunctionResponse(
                                            id=function_call.id,
                                            name=function_call.name,
                                            response=function_result
                                        )
                                    ]
                                    await session.send_tool_response(function_responses=function_responses)
                                    logger.debug(f"Function response sent successfully via send_tool_response")
                                except Exception as e:
                                    logger.error(f"Failed to send function response: {e}")
                                    logger.error(f"Continuing without sending response...")
                                
                            except Exception as e:
                                logger.error(f"Function execution error: {e}")
                                # Don't try to send error response for now - just continue
                        
                        yield response_data
                
                # Handle tool call cancellations
                if hasattr(response, 'tool_call_cancellation') and response.tool_call_cancellation:
                    logger.debug(f"Tool call cancelled: {response.tool_call_cancellation.ids}")
                    response_data["type"] = "function_cancelled"
                    response_data["cancelled_ids"] = response.tool_call_cancellation.ids
                    yield response_data
                
                # Handle session resumption updates
                if hasattr(response, 'session_resumption_update') and response.session_resumption_update:
                    update = response.session_resumption_update
                    logger.info(f"Session resumption update: resumable={getattr(update, 'resumable', False)}, has_handle={hasattr(update, 'new_handle')}")
                    
                    response_data["type"] = "session_resumption_update"
                    response_data["resumption_data"] = {
                        "resumable": getattr(update, 'resumable', False),
                        "new_handle": getattr(update, 'new_handle', None)
                    }
                    yield response_data
        
        except asyncio.CancelledError:
            logger.info("Response processing cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in process_responses: {e}")
            raise
        finally:
            logger.info("Finished Gemini Live response processing")
    
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