# Gmail Voice Assistant - Implementation Details

## 🏗️ Overall Architecture

Your codebase implements a **real-time voice-first Gmail assistant** using a multi-layer architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PyAudio       │    │   FastAPI       │    │   Gemini Live   │
│   Client        │◄──►│   WebSocket     │◄──►│   API           │
│                 │    │   Server        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Gmail API     │
                       │   + Redis       │
                       └─────────────────┘
```

## 🔐 Authentication Flow

### 1. **Firebase Authentication** (`src/api/middleware/auth.py`)
```
User Token → Firebase Validation → User ID Extraction
```

### 2. **Gmail OAuth Flow** (`src/api/controllers/auth_controller.py`)
```
/api/auth/gmail/authorize → Google OAuth → /api/auth/gmail/callback → Store in Redis
```

### 3. **Credential Storage** (`src/core/auth/user_credential_store.py`)
```python
# Redis Structure
redis_key = "gmail_creds:{user_id}"
stored_data = {
    "token": "access_token",
    "refresh_token": "refresh_token", 
    "client_id": "oauth_client_id",
    "client_secret": "oauth_secret",
    "scopes": ["gmail.modify", "gmail.compose"]
}
```

## 🔌 WebSocket Communication Flow

### **Entry Point**: `src/api/controllers/voice_controller.py`
```python
@router.websocket("/voice")
async def voice_websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
```

### **Connection Flow**:
```
1. Client connects with Firebase token
2. VoiceWebSocketHandler.connect() validates auth
3. Retrieves Gmail credentials from Redis  
4. Initializes Gemini Live session
5. Starts bidirectional communication
```

### **Key Components**:

#### **Client** (`src/clients/pyaudio_client.py`):
```python
# Audio Input: Microphone → PyAudio → Base64 → WebSocket
# Audio Output: WebSocket → Base64 → PyAudio → Speakers
# Message Types: start_voice_session, audio_chunk, end_voice_session
```

#### **Server Handler** (`src/api/websocket/voice_handler.py`):
```python
class VoiceWebSocketHandler:
    # Manages per-user connections
    self.active_connections: Dict[str, Dict[str, Any]] = {
        "user_id": {
            "websocket": websocket,
            "gmail_service": GmailService(),
            "function_handler": GmailFunctionHandler(),
            "gemini_client": GeminiLiveClient(),
            "gemini_session": session
        }
    }
```

## 🎙️ Gemini Live API Integration

### **Core Component**: `src/core/voice/gemini_live_client.py`

#### **Session Management**:
```python
# 1. Create session context manager
session_context = client.aio.live.connect(model="gemini-2.5-flash-live-preview", config=config)

# 2. Enter session  
gemini_session = await session_context.__aenter__()

# 3. Process responses
async for response in session.receive():
    # Handle tool_call, server_content, audio, etc.
```

#### **Function Definitions**:
```python
functions = [
    {
        "name": "read_messages",
        "description": "Fetch and read Gmail messages", 
        "parameters": {
            "filter_type": {"enum": ["unread", "important", "starred", "all"]},
            "max_results": {"type": "integer"},
            "read_full": {"type": "boolean"}
        }
    },
    # navigate_messages, summarize_message, mark_message, draft_email
]
```

#### **Audio Processing**:
```python
# Send audio to Gemini
await session.send_realtime_input(audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000"))

# Receive audio from Gemini  
if response.server_content.model_turn.parts[0].inline_data:
    audio_data = part.inline_data.data
```

#### **Function Call Handling**:
```python
# Detect function calls
if response.tool_call:
    for function_call in response.tool_call.function_calls:
        # Execute Gmail function
        result = await function_handler.handle_function_call({
            "name": function_call.name,
            "parameters": function_call.args,
            "id": function_call.id
        })
        
        # Send response back to Gemini
        await session.send_tool_response(function_responses=[
            types.FunctionResponse(
                id=function_call.id,
                name=function_call.name, 
                response=result
            )
        ])
```

## 📧 Gmail API Function Calls

### **Function Handler**: `src/core/voice/function_handler.py`

#### **Available Functions**:

1. **`read_messages`** - Primary email reading function
2. **`navigate_messages`** - Next/previous navigation  
3. **`summarize_message`** - AI summarization
4. **`mark_message`** - Change email status
5. **`draft_email`** - Create/send emails

#### **Gmail Service**: `src/core/gmail_client/gmail_service.py`

```python
class GmailService:
    # Core API methods
    def list_messages(self, query="", max_results=10) -> List[str]
    def get_message(self, message_id: str) -> Dict[str, Any]  
    def modify_message(self, message_id: str, add_labels=[], remove_labels=[])
    def create_draft(self, to: str, subject: str, body: str) -> str
    def send_draft(self, draft_id: str) -> str
```

#### **Session Management**: `src/core/session/session_manager.py`

```python
# Redis session state per user
session_state = {
    "current_message_id": "gmail_msg_id",
    "message_queue": ["msg_1", "msg_2", "msg_3"],
    "current_filter": "unread", 
    "current_index": 0,
    "total_messages": 15,
    "next_page_token": "pagination_token"
}
```

## 🔄 Complete Voice Flow Sequence

### **User Says "Read my Gmail"**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           VOICE PROCESSING FLOW                        │
└─────────────────────────────────────────────────────────────────────────┘

1. 🎤 PyAudio Client (pyaudio_client.py)
   ├── Records audio from microphone
   ├── Encodes as Base64
   └── Sends via WebSocket: {"type": "audio_chunk", "data": "base64_audio"}

2. 🔌 WebSocket Handler (voice_handler.py)  
   ├── Receives audio chunk
   ├── Forwards to Gemini Live session
   └── await gemini_client.send_realtime_input(audio_data)

3. 🤖 Gemini Live API (gemini_live_client.py)
   ├── Processes speech → "read my gmail" 
   ├── Matches to function definition: "read_messages"
   └── Returns: tool_call.function_calls[0] = {name: "read_messages", args: {...}}

4. ⚡ Function Handler (function_handler.py)
   ├── Receives function call
   ├── Maps to: await self.read_messages(**parameters)
   └── Calls Gmail API via GmailService

5. 📧 Gmail Service (gmail_service.py)
   ├── Uses stored OAuth credentials
   ├── Calls Gmail API: service.users().messages().list()
   ├── Fetches message details: service.users().messages().get()
   └── Returns formatted email data

6. 📤 Response Flow
   ├── Function result sent back to Gemini: session.send_tool_response()
   ├── Gemini generates speech response with email content
   ├── Audio streamed back via WebSocket
   └── PyAudio plays response through speakers

7. 🔄 Session State (session_manager.py)
   ├── Updates Redis with current message index
   ├── Stores message queue for navigation
   └── Maintains conversation context
```

## 🎯 Key Strengths & Current Issues

### **✅ Strengths**:
- **Modular architecture** - Clear separation of concerns
- **Real-time audio** - Bidirectional streaming with Gemini Live API
- **Multi-user support** - Per-user sessions and credentials
- **Function calling** - Natural language → Gmail operations
- **State management** - Redis for navigation and context

### **🔧 Issues Fixed**:
- **WebSocket timing** - Accept before credential check
- **Function response format** - Correct API method usage (`send_tool_response`)
- **Session management** - Proper context manager handling
- **Error handling** - Graceful degradation on failures

### **💡 Architecture Benefits**:
- **Scalable** - Can handle multiple concurrent users
- **Extensible** - Easy to add new functions (calendar, contacts, etc.)
- **Voice-first** - Optimized for hands-free operation
- **Secure** - Firebase auth + OAuth token management

## 🔧 Technical Implementation Details

### **File Structure & Responsibilities**:

```
src/
├── api/
│   ├── controllers/
│   │   ├── voice_controller.py     # WebSocket endpoint definition
│   │   └── auth_controller.py      # Gmail OAuth flow
│   ├── middleware/
│   │   └── auth.py                 # Firebase token validation
│   └── websocket/
│       └── voice_handler.py        # WebSocket session management
├── core/
│   ├── auth/
│   │   └── user_credential_store.py # Redis credential storage
│   ├── voice/
│   │   ├── gemini_live_client.py   # Gemini Live API wrapper
│   │   └── function_handler.py     # Gmail function execution
│   ├── gmail_client/
│   │   └── gmail_service.py        # Gmail API operations
│   └── session/
│       └── session_manager.py      # Redis session state
└── clients/
    └── pyaudio_client.py           # Test audio client
```

### **Key Configuration**:

#### **Gemini Live Session Config**:
```python
config = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "You are a helpful Gmail voice assistant...",
    "tools": [{"function_declarations": gmail_functions}]
}
```

#### **Audio Parameters**:
```python
INPUT_RATE = 16000   # Client audio input
OUTPUT_RATE = 24000  # Gemini audio output
FORMAT = pyaudio.paInt16
CHANNELS = 1
CHUNK = 1024
```

#### **Redis Keys**:
```python
gmail_credentials = f"gmail_creds:{user_id}"
user_session = f"user_sessions:{user_id}"
draft_storage = f"draft_storage:{user_id}"
```

## 🚀 Next Improvement Areas

1. **Audio Quality** - Add noise cancellation, better encoding
2. **Function Expansion** - More Gmail operations (search, filters, labels)
3. **Context Awareness** - Better conversation memory
4. **Error Recovery** - Retry mechanisms for API failures
5. **Performance** - Connection pooling, caching strategies
6. **Testing** - Unit tests for each component
7. **Monitoring** - Logging and metrics collection
8. **Security** - Rate limiting, input validation

## 🐛 Common Debugging Points

### **WebSocket Issues**:
- Check Firebase token validity
- Verify Gmail credential storage in Redis
- Monitor WebSocket connection state

### **Audio Problems**:
- PyAudio device configuration
- Audio encoding/decoding mismatches
- WebSocket message size limits

### **Function Call Failures**:
- Gmail API quota limits
- OAuth token expiration
- Function parameter validation

### **Session Management**:
- Redis connection health
- Session state corruption
- Concurrent user handling

This architecture provides a solid foundation for a production voice assistant!