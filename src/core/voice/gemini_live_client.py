import asyncio
from typing import Dict, Any, Optional, Callable, AsyncGenerator
from google import genai
from google.genai import types


class GeminiLiveClient:
    """Gemini Live API client for streaming voice processing"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash-live-preview"
        
        # Function definitions for Gmail operations
        self.functions = [
            {
                "name": "read_messages",
                "description": "Fetch and read Gmail messages",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter_type": {
                            "type": "string",
                            "enum": ["unread", "important", "starred", "all"],
                            "description": "Type of messages to fetch"
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
                        "recipient": {"type": "string", "description": "Email recipient"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "content": {"type": "string", "description": "Email body content"},
                        "modifications": {"type": "string", "description": "Specific changes for editing"}
                    }
                }
            }
        ]
    
    def get_session_config(self) -> Dict[str, Any]:
        """Get configuration for Gemini Live session"""
        return {
            "response_modalities": ["AUDIO"],
            "system_instruction": """You are a helpful Gmail voice assistant. You can:
            
1. Read emails aloud - When users ask to read messages, immediately fetch and read the first one
2. Navigate through messages using next/previous commands
3. Summarize emails with key points and action items
4. Mark messages as read, starred, etc.
5. Create and manage email drafts
6. Search for specific messages by sender or topic

Always provide natural, conversational responses. When reading emails, format content for voice delivery (convert timestamps to natural language, break long emails into digestible chunks).

For "read my messages" commands:
1. Fetch the messages
2. Immediately read the first message aloud
3. Let user know navigation options ("say next message to continue")

Keep responses concise but informative. Ask for clarification when needed.""",
            "tools": [{"function_declarations": self.functions}]
        }
    
    async def create_session(self, function_handler: Callable = None):
        """Create streaming session with function calling support"""
        config = self.get_session_config()
        
        session = await self.client.aio.live.connect(
            model=self.model,
            config=config
        )
        
        # Store function handler for processing function calls
        session._function_handler = function_handler
        
        return session
    
    async def send_audio_chunk(self, session, audio_data: bytes, mime_type: str = "audio/pcm;rate=16000"):
        """Send audio chunk to Gemini Live API"""
        await session.send_realtime_input(
            audio=types.Blob(
                data=audio_data,
                mime_type=mime_type
            )
        )
    
    async def process_responses(self, session, function_handler: Callable = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Process responses from Gemini Live API and handle function calls"""
        async for response in session.receive():
            response_data = {
                "type": "response",
                "data": None,
                "text": None,
                "function_call": None,
                "audio_data": None
            }
            
            # Handle audio response
            if hasattr(response, 'data') and response.data:
                response_data["type"] = "audio"
                response_data["audio_data"] = response.data
                yield response_data
            
            # Handle text response (for debugging)
            if hasattr(response, 'text') and response.text:
                response_data["type"] = "text"
                response_data["text"] = response.text
                yield response_data
            
            # Handle function calls
            if hasattr(response, 'function_call') and response.function_call:
                response_data["type"] = "function_call"
                response_data["function_call"] = response.function_call
                
                # Execute function if handler provided
                if function_handler:
                    try:
                        function_result = await function_handler(response.function_call)
                        # Send function result back to Gemini
                        await session.send_function_response(function_result)
                    except Exception as e:
                        print(f"Function execution error: {e}")
                        await session.send_function_response({
                            "error": str(e)
                        })
                
                yield response_data
    
    async def send_text_input(self, session, text: str):
        """Send text input to session (for debugging)"""
        await session.send(text)
    
    def format_voice_response(self, text: str) -> str:
        """Format text for natural voice delivery"""
        import re
        from datetime import datetime
        
        # Convert timestamps to natural language
        # This is a simplified version - you might want more sophisticated parsing
        formatted = text
        
        # Remove excessive whitespace
        formatted = re.sub(r'\s+', ' ', formatted)
        
        # Add natural pauses for better voice delivery
        formatted = formatted.replace('\n', ' ... ')
        formatted = formatted.replace('. ', '. ')
        
        return formatted.strip()