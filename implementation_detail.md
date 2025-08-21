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
    # Manages per-user connections with automatic task monitoring
    self.active_connections: Dict[str, Dict[str, Any]] = {
        "user_id": {
            "websocket": websocket,
            "gmail_service": GmailService(),
            "function_handler": GmailFunctionHandler(),
            "gemini_client": GeminiLiveClient(),
            "gemini_session": session,
            "response_task": asyncio.Task,        # NEW: Monitors response processing
            "session_context": context_manager    # NEW: Proper session cleanup
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
- Defines Gmail operations as Gemini function schemas
- Includes read_messages, navigate_messages, summarize_message, mark_message, draft_email

#### **Audio Processing**:
- Send: `session.send_realtime_input(audio=types.Blob(...))`
- Receive: Extract audio from `response.server_content.model_turn.parts[0].inline_data`

#### **Function Call Handling**:
- Detect: `if response.tool_call:` iterate through function calls
- Execute: `await function_handler.handle_function_call(...)` 
- Respond: `await session.send_tool_response(function_responses=[...])`

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
- Redis session state: current_message_id, message_queue, current_filter, current_index, pagination tokens

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
- **⚡ Voice Processing Continuity** - Automatic task restart for continuous voice interactions

### **💡 Architecture Benefits**:
- **Scalable** - Can handle multiple concurrent users
- **Extensible** - Easy to add new functions (calendar, contacts, etc.)
- **Voice-first** - Optimized for hands-free operation
- **Secure** - Firebase auth + OAuth token management

## 🔄 Voice Processing Task Management

### **Problem Solved**: Continuous Voice Interaction
The original implementation had a critical issue where voice commands after the first interaction were ignored due to response processing tasks completing normally and not being restarted.

### **Solution**: Automatic Task Restart System

#### **Key Components**:

1. **Task Monitoring** (`voice_handler.py:_start_response_processing`)
   - Creates asyncio task for Gemini response processing
   - Adds completion callback to monitor task lifecycle
   - Handles both normal completion and error cases

2. **Automatic Recovery** (`voice_handler.py:_restart_response_processing`)
   - Automatically restarts response processing when tasks complete
   - Validates session state before restart
   - Provides user feedback on recovery status

3. **Enhanced Error Handling** (`voice_handler.py:_process_gemini_responses`)
   - Connection validation during processing loop
   - Individual response error isolation
   - Proper cancellation and cleanup handling

4. **Improved Logging** (`gemini_live_client.py:process_responses`)
   - Comprehensive lifecycle logging
   - Response counting and debugging information
   - Error tracking and recovery monitoring

### **Flow**:
```
Voice Input → Response Processing Task → Task Completes → Callback Triggered → 
New Task Started → Ready for Next Voice Input
```

### **Benefits**:
- ✅ **Continuous Operation**: Voice commands work indefinitely without reconnection
- ✅ **Error Recovery**: Automatic restart on both failures and normal completion  
- ✅ **Detailed Monitoring**: Enhanced logging for production debugging
- ✅ **Graceful Cleanup**: Proper task lifecycle management

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
- `response_modalities: ["AUDIO"]`, system instructions, function declarations

#### **Audio Parameters**:
- Input: 16kHz PCM, Output: 24kHz PCM, Format: paInt16, Mono channel

#### **Redis Keys**:
- `gmail_creds:{user_id}`, `user_sessions:{user_id}`, `draft_storage:{user_id}`

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