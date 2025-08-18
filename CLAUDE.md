# Gmail Voice Assistant - Technical Plan

## Project Overview
Building a voice-first Gmail assistant that enables hands-free email management through natural language voice interactions using Gemini Live API with streaming audio processing, FastAPI backend, and multi-user support.

## Architecture Design

### Modular Structure
```
gmail-assistant/
├── src/
│   ├── api/                  # FastAPI application
│   │   ├── auth/             # Authentication endpoints & middleware
│   │   ├── websocket/        # Streaming voice WebSocket handler
│   │   └── main.py           # FastAPI app initialization
│   ├── core/
│   │   ├── auth/             # Firebase Auth + Gmail OAuth integration
│   │   ├── gmail_client/     # Gmail API integration
│   │   ├── voice/            # Voice processing & Gemini Live API
│   │   ├── session/          # Redis session management
│   │   └── processors/       # Message processing & analysis
│   ├── clients/              # Test clients
│   │   └── pyaudio_client/   # PyAudio streaming test client
│   ├── utils/                # Utilities & helpers
│   └── config/               # Configuration management
├── tests/                    # Unit & integration tests
├── requirements.txt          # Dependencies
└── main.py                   # FastAPI server entry point
```

## Core Components

### 1. Authentication Layer (`src/core/auth/`)
- **firebase_auth.py**: Firebase authentication integration & token validation
- **gmail_oauth.py**: Gmail OAuth2 credential management
- **token_manager.py**: Token refresh & storage for Gmail tokens

### 2. Gmail API Client (`src/core/gmail_client/`)
- **gmail_service.py**: Unified Gmail operations (read, modify, drafts, search) - EXISTING ✅
- **error_handler.py**: API error handling with retry logic

### 3. Voice Processing (`src/core/voice/`)
- **gemini_live_client.py**: Gemini Live API integration for streaming audio
- **function_handler.py**: Intent recognition and Gmail function calling logic
- **response_formatter.py**: Format email content for natural voice delivery

### 4. Session Management (`src/core/session/`)
- **redis_client.py**: Redis connection and operations
- **session_manager.py**: User session state and navigation context
- **draft_storage.py**: Temporary draft storage using Redis internally

### 5. Message Processing (`src/core/processors/`)
- **message_parser.py**: Extract and clean email content for voice delivery

### 6. FastAPI Application (`src/api/`)
- **main.py**: FastAPI app with WebSocket support
- **auth_endpoints.py**: Firebase login and Gmail OAuth endpoints
- **auth_middleware.py**: Firebase token validation middleware
- **voice_websocket.py**: Streaming voice WebSocket endpoint

### 7. PyAudio Test Client (`src/clients/`)
- **pyaudio_client.py**: Simple streaming audio client that connects to our WebSocket service

## Voice Processing with Gemini Live API

### Voice Command Examples
Users can speak requests naturally:
- "Read my unread emails"
- "Summarize this message"
- "Mark as read and go to next message"
- "Draft a reply saying I'll be there"
- "What are my starred messages?"
- "Find emails from my boss about the project"

### Function Calling Integration
Gemini Live API processes voice input and calls appropriate functions:
- **read_messages**: Fetch messages and immediately read first one
- **navigate_messages**: Session-based navigation with Gmail API pagination fallback
- **summarize_message**: Summarize current message using Gemini Live API
- **mark_message**: Change message status (read/unread/star/archive)
- **draft_email**: Create, edit, save, or send email drafts

### Navigation Logic
- **Session Cache**: Messages stored in Redis for smooth "next/previous" navigation
- **Immediate Response**: "Read my unread messages" → fetch + immediately read first message
- **Smart Pagination**: At last message → fetch next batch using Gmail nextPageToken if available
- **End Handling**: No more messages → "That was the last message. Would you like to check other messages?"

## Technical Implementation

### Streaming Voice Processing Pipeline
1. **Voice Input**: Real-time audio streaming via WebSocket
2. **Gemini Live API**: Process audio stream with function calling
3. **Function Execution**: Execute Gmail operations based on intent
4. **Session Update**: Update Redis session state and navigation context
5. **Voice Response**: Stream audio response back to user in real-time

### Authentication & Token Management
- **Firebase Auth**: User authentication and session validation
- **Gmail OAuth**: Access and refresh token management
- **Centralized Storage**: Single Redis hash for all user tokens
- **Auto-refresh**: Automatic token refresh before expiration

### Gmail API Integration
- **Scopes**: `gmail.modify` for read/mark operations, `gmail.compose` for drafts
- **Session Management**: Redis for navigation state and temporary drafts
- **Smart Pagination**: Use nextPageToken for seamless message navigation
- **Error Handling**: Graceful handling of quota limits & network issues

### WebSocket Streaming Architecture
- **Real-time Audio**: Bidirectional audio streaming for natural conversation
- **Session Persistence**: Maintain conversation context across WebSocket connection
- **Function Calling**: Gemini Live API triggers Gmail operations via function calls
- **Low Latency**: Start processing before user finishes speaking

## Dependencies & Requirements
- `fastapi` (Web framework with WebSocket support)
- `uvicorn` (ASGI server for FastAPI)
- `websockets` (WebSocket client/server implementation)
- `redis` (Redis client for session management)
- `firebase-admin` (Firebase authentication)
- `google-auth==2.3.3` (Google authentication)
- `google-api-python-client==2.31.0` (Gmail API client)
- `google-genai` (Gemini Live API SDK)
- `pyaudio` (Audio recording/playback for test client)
- `pydantic` (Data validation)
- `python-dotenv` (Environment management)

## Development Phases
1. **Phase 1**: FastAPI backend with Firebase Auth + Gmail OAuth integration
2. **Phase 2**: Redis session management and user token storage
3. **Phase 3**: Basic Gmail API client (unified read/modify/draft operations)
4. **Phase 4**: Gemini Live API integration with function calling
5. **Phase 5**: WebSocket streaming voice endpoint implementation
6. **Phase 6**: PyAudio test client for voice interaction testing
7. **Phase 7**: Navigation logic and session-based message handling
8. **Phase 8**: Testing, optimization, and CarPlay preparation

## Redis Database Design

### Single Hash Structure for All Data
All user data stored in centralized Redis hashes for efficient operations:

```redis
# User tokens (all users in one hash)
user_tokens = {
  "firebase_uid_1": {
    "firebase_token": "jwt_token",
    "gmail_access_token": "access_token",
    "gmail_refresh_token": "refresh_token", 
    "gmail_token_expires": 1234567890,
    "gmail_authorized": true,
    "last_refreshed": 1234567890
  },
  "firebase_uid_2": { ... }
}

# User sessions (all users in one hash)
user_sessions = {
  "firebase_uid_1": {
    "current_message_id": "gmail_msg_id",
    "message_queue": ["msg_id_1", "msg_id_2"],
    "current_filter": "unread",
    "current_index": 0,
    "total_messages": 15,
    "next_page_token": "token_xyz",
    "last_active": 1234567890
  },
  "firebase_uid_2": { ... }
}

# Draft storage (all users in one hash)
draft_storage = {
  "firebase_uid_1": {
    "recipient": "john@example.com",
    "subject": "Meeting follow-up",
    "content": "Draft content...",
    "reply_to_message_id": "gmail_msg_id",
    "created_at": 1234567890,
    "status": "editing"
  },
  "firebase_uid_2": { ... }
}
```

### Redis Operations
- Get user data: `HGET user_tokens firebase_uid`
- Update tokens: `HSET user_tokens firebase_uid {updated_data}`
- Session management: `HGET/HSET user_sessions firebase_uid`
- Draft operations: `HGET/HSET draft_storage firebase_uid`

## Security & Configuration
- **Credential Security**: Secure token storage, no hardcoded secrets
- **Input Validation**: Sanitize user inputs & email content
- **Privacy**: No logging of email content or personal data
- **Rate Limiting**: Respect Gmail API quotas
- **Error Handling**: Graceful degradation for API failures