import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from google import genai
from google.genai import types

from app.config import settings
from app.schemas.config import PREBUILT_PERSONAS, INSTRUCTION_PRESETS


logger = logging.getLogger(__name__)


class GeminiLiveClient:
    """Gemini Live API client for streaming voice processing"""

    def __init__(self, voice_persona: dict = None):
        # Get API key from settings
        api_key = settings.GEMINI_API_KEY

        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError(
                "Gemini API key is required. Please set the settings.GEMINI_API_KEY environment variable. "
                "You can get an API key from https://makersuite.google.com/app/apikey"
            )

        logger.info("Initializing Gemini Live client with API key from settings")
        timeout_ms = settings.GEMINI_HTTP_TIMEOUT
        logger.info(f"Setting Gemini HTTP timeout to {timeout_ms}ms ({timeout_ms/60000:.1f} minutes)")
        http_options = genai.types.HttpOptions(timeout=timeout_ms)
        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = "gemini-3.1-flash-live-preview"

        # Resolve voice persona
        self.voice_persona = voice_persona or {}
        persona_id = self.voice_persona.get("persona_id", "default")
        persona = PREBUILT_PERSONAS.get(persona_id, PREBUILT_PERSONAS["default"])

        self.resolved_voice = self.voice_persona.get("voice_name") or persona["default_voice"]
        self.resolved_name = self.voice_persona.get("persona_name") or persona["name"]
        # Prefer the rich persona_instructions library; fall back to short style_prompt
        self.resolved_persona_instructions = (
            persona.get("persona_instructions") or persona["style_prompt"]
        )
        # User-set language overrides persona default. If neither is set, no language
        # directive is emitted and the model simply mirrors the user's spoken language.
        self.resolved_language = (
            self.voice_persona.get("language") or persona.get("default_language")
        )
        self.enable_transcription = self.voice_persona.get("enable_transcription", True)

        # Resolve custom instructions (expand preset IDs)
        custom = self.voice_persona.get("custom_instructions")
        if custom and custom in INSTRUCTION_PRESETS:
            self.resolved_custom_instructions = INSTRUCTION_PRESETS[custom]["instructions"]
        else:
            self.resolved_custom_instructions = custom

        logger.info(f"Persona: {self.resolved_name} ({persona_id}), voice: {self.resolved_voice}, lang: {self.resolved_language}")

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
                            "enum": ["read", "unread", "star", "unstar", "archive", "trash", "delete"],
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
            },
            {
                "name": "get_attachments",
                "description": (
                    "List or describe attachments on the current message. "
                    "Use action='list' to see all attachments with filenames and sizes. "
                    "Use action='describe' with attachment_index to get an AI-generated "
                    "summary of a specific attachment's content (supports PDFs, images, CSVs, etc.)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["list", "describe"],
                            "description": "'list' to enumerate attachments, 'describe' to summarize one"
                        },
                        "attachment_index": {
                            "type": "integer",
                            "description": "0-based index of attachment to describe (required when action='describe')"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "read_thread",
                "description": (
                    "Read the full email conversation thread for the current message. "
                    "Returns all messages in the thread in chronological order. "
                    "Use when the user asks for the full conversation, thread, or history."
                ),
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "list_labels",
                "description": (
                    "List all Gmail labels available to the user, including custom user labels "
                    "and system labels. Use when the user asks what labels they have."
                ),
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "modify_labels",
                "description": (
                    "Add or remove a label on the current message. Invoke only when the user "
                    "explicitly asks to label, categorize, tag, or move a message to a label. "
                    "If the user uses a label you don't recognize, call list_labels first."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["add", "remove"],
                            "description": "Whether to add or remove the label"
                        },
                        "label_name": {
                            "type": "string",
                            "description": "Name of the label (matched case-insensitively)"
                        }
                    },
                    "required": ["action", "label_name"]
                }
            },
            {
                "name": "search_contacts",
                "description": (
                    "Search for email addresses by name from recent email history. "
                    "Use when the user wants to send an email but only provides a name "
                    "without an address, e.g. 'send email to John'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name_query": {
                            "type": "string",
                            "description": "Name or partial name/email to search for"
                        }
                    },
                    "required": ["name_query"]
                }
            }
        ]
    
    def _build_system_instruction(self) -> str:
        """Build structured system instruction following Gemini Live API best practices.

        Structure: Persona -> Conversational Rules -> Tool Usage Rules -> Guardrails
        """
        sections = []

        # --- PERSONA ---
        persona_section = (
            "## PERSONA\n"
            f"You are a voice-based Gmail assistant. You help users read, navigate, summarize, label, "
            "and reply to emails using voice only. Everything you say will be spoken aloud — never type.\n\n"
            f"{self.resolved_persona_instructions}\n\n"
            "Stay in character UNMISTAKABLY throughout the entire conversation. "
            "Your persona is the primary flavor of every response — but never let it obscure the actual "
            "email content or the correctness of any action you take."
        )

        # Language directive — highest priority. Falls back to user-language matching
        # when no default language is set for this persona.
        if self.resolved_language:
            language_section = (
                "## LANGUAGE (HIGHEST PRIORITY)\n"
                f"Speak in {self.resolved_language} by default. "
                "If the user speaks to you in a different language, switch to their language "
                "and continue in it until they switch back. Match any code-mixed variant "
                "(e.g. Hinglish) naturally. This rule overrides every persona and style directive below.\n\n"
            )
        else:
            language_section = (
                "## LANGUAGE (HIGHEST PRIORITY)\n"
                "Detect the language the user is speaking in and respond in that SAME language. "
                "If the user switches languages mid-conversation, switch with them. Match any "
                "code-mixed variant (e.g. Hinglish) naturally. This rule overrides every persona "
                "and style directive below.\n\n"
            )
        persona_section = language_section + persona_section

        if self.resolved_custom_instructions:
            persona_section += (
                f"\n\n**Additional style directive:** {self.resolved_custom_instructions}"
            )

        sections.append(persona_section)

        # --- CONVERSATIONAL RULES ---
        sections.append(
            "## CONVERSATIONAL RULES\n\n"
            "**One-time — conversation opening:**\n"
            "1. When the user first speaks (even if only to say 'hi'), greet them as "
            f"{self.resolved_name} using the greeting style from your persona definition, then ask "
            "what they'd like to do with their inbox. Do NOT launch into reading emails until asked.\n\n"
            "**Conversational loop — for the rest of the session:**\n"
            "2. Respond naturally and conversationally in your persona's voice.\n"
            "3. Format all content for the ear, not the eye: say dates as natural language "
            "('yesterday', 'two hours ago', 'last Tuesday'), never read URLs or message IDs aloud.\n"
            "4. Keep responses short. For long emails, read the sender, subject, and a 1–2 sentence "
            "summary first, then ask if the user wants the full content.\n"
            "5. When reading any email, always announce sender → subject → date → content, in that order.\n"
            "6. If a request is ambiguous, ask ONE concise clarifying question.\n"
            "7. Let the user steer the conversation — they may jump between reading, replying, "
            "labeling, and searching freely. That is expected; engage with whatever topic they bring up."
        )

        # --- TOOL USAGE RULES ---
        sections.append("""## TOOL USAGE RULES

**Reading emails — use read_messages():**
- When the user says "read my messages", "check my email", etc., call read_messages()
- Immediately read the first message aloud after fetching
- Let the user know navigation options ("say next message to continue")

**Navigating — use navigate_messages():**
- ALWAYS use navigate_messages() for ANY navigation request including:
  "next message", "previous message", "go to next", "go to previous",
  "read my next message", "first message", "last message"
- For "read next/previous/first/last message" commands, prioritize navigate_messages() over read_messages()
- NEVER assume there are no more messages — let navigate_messages() check session state and pagination tokens
- The function will automatically fetch more messages if available using pagination
- Do NOT give responses like "no more messages" or "you've reached the end" without calling navigate_messages() first

**Drafts and replies — use draft_email():**
- Use reply_to=true for: "reply to this message", "respond to this email", "write back to them", "reply that..."
- Use reply_to=false for: "create new email", "send email to [person]", "draft an email to..."
- When reply_to=true, only provide content — recipient and subject auto-populate from the current message
- When reply_to=false, all parameters (recipient, subject, content) are required

**Marking messages — use mark_message():**
- Invoke only when the user explicitly asks to mark, star, archive, or trash a message
- Supported actions: read, unread, star, unstar, archive, trash

**Summarizing — use summarize_message():**
- Invoke when the user asks for a summary or key points of the current message

**Attachments — use get_attachments():**
- When the user asks "does this email have attachments?" or "what's attached", call with action='list'
- When the user asks "what's in that PDF?" or "read the attachment", call with action='describe' and the attachment_index
- After listing, if the user refers to "the first one" / "the second attachment", use the matching 0-based index

**Threads — use read_thread():**
- Use when the user asks to "read the whole conversation", "show the thread", or "what did they say before"

**Labels — use list_labels() and modify_labels():**
- Use list_labels() when the user asks what labels they have
- Use modify_labels() only when the user explicitly asks to label, categorize, or tag the current message
- If you don't know the exact label name, call list_labels() first

**Contacts — use search_contacts():**
- Use when the user wants to email someone but only provides a name (e.g. "send email to John")
- After finding the email, ask the user to confirm before drafting""")

        # --- GUARDRAILS ---
        sections.append(
            "## GUARDRAILS\n"
            "- NEVER fabricate email content. Only say what is actually in the tool results.\n"
            "- NEVER send an email without unmistakably confirming with the user first. "
            "If the user says 'draft', only draft. Only send after an explicit 'send it' / 'yes send'.\n"
            "- Always confirm before performing destructive actions (trash, archive, delete label).\n"
            "- NEVER spell out email addresses character by character. Say 'john at example dot com'.\n"
            "- NEVER read message IDs, thread IDs, or long random strings aloud.\n"
            "- NEVER speak stage directions, sound effects, music cues, emotion labels, or parenthetical "
            "notes out loud. Do NOT say things like '[DRAMATIC MUSIC]', '[GASP]', '[WHISPER]', "
            "'(pause)', 'dramatic whisper', 'sound effect' etc. Express emotion and drama through your "
            "actual voice — tone, pacing, volume, and word choice — never by narrating the direction.\n"
            "- When the actual email content matters (numbers, dates, names, amounts), "
            "prioritize clarity over persona flair — the user must unmistakably understand the facts.\n"
            "- If the user asks for something outside your Gmail capabilities, say so politely in character."
        )

        return "\n\n".join(sections)

    def get_session_config(self) -> types.LiveConnectConfig:
        """Get configuration for Gemini Live session with context compression, session resumption, and voice persona."""
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],

            # Voice selection
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.resolved_voice,
                    )
                )
            ),

            # Enable context window compression with sliding window
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),

            # Always enable session resumption (handle will be set during session creation)
            session_resumption=types.SessionResumptionConfig(),

            # Realtime input configuration
            realtime_input_config=types.RealtimeInputConfig(),

            # Structured system instruction
            system_instruction=types.Content(
                parts=[types.Part(text=self._build_system_instruction())]
            ),

            # Function calling tools
            tools=[types.Tool(function_declarations=self.functions)],
        )

        # Enable transcription if configured
        if self.enable_transcription:
            config.input_audio_transcription = types.AudioTranscriptionConfig()
            config.output_audio_transcription = types.AudioTranscriptionConfig()

        return config
    
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

                    # Check for interruption (user started speaking - VAD detected)
                    if hasattr(server_content, 'interrupted') and server_content.interrupted:
                        logger.info(f"Gemini VAD detected user interruption - generation cancelled")
                        response_data["type"] = "interrupted"
                        response_data["message"] = "User interrupted - stop audio playback"
                        yield response_data
                        continue  # Skip processing rest of this response

                    # Check for generation_complete signal
                    if hasattr(server_content, 'generation_complete') and server_content.generation_complete:
                        logger.debug("Generation complete signal received")
                        yield {"type": "generation_complete", "data": None, "text": None, "function_call": None, "audio_data": None}

                    # Check for input transcription
                    if hasattr(server_content, 'input_transcription') and server_content.input_transcription:
                        text = getattr(server_content.input_transcription, 'text', None)
                        if text:
                            logger.debug(f"Input transcription: {text}")
                            yield {"type": "input_transcription", "text": text, "data": None, "function_call": None, "audio_data": None}

                    # Check for output transcription
                    if hasattr(server_content, 'output_transcription') and server_content.output_transcription:
                        text = getattr(server_content.output_transcription, 'text', None)
                        if text:
                            logger.debug(f"Output transcription: {text}")
                            yield {"type": "output_transcription", "text": text, "data": None, "function_call": None, "audio_data": None}

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

                                # Always attach result to response data for the client
                                response_data["function_result"] = function_result

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
                                response_data["function_result"] = {"error": str(e)}
                        
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

                # Handle GoAway message (connection will soon terminate)
                if hasattr(response, 'go_away') and response.go_away:
                    time_left = getattr(response.go_away, 'time_left', None)
                    logger.warning(f"Received GoAway message, time_left={time_left}")
                    yield {
                        "type": "goaway",
                        "data": None, "text": None, "function_call": None, "audio_data": None,
                        "goaway_data": {"time_left": str(time_left) if time_left else None}
                    }
        
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
