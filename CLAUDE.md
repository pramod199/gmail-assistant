# Gmail Voice Assistant - Technical Plan

## IMPORTANT: Development Guidelines
- **NO Documentation Files**: Do NOT create README.md, API documentation, or any .md files unless explicitly requested by the user
- **Focus on Implementation**: Prioritize writing actual code over documentation
- **Code is Documentation**: Write clean, self-documenting code with clear naming and docstrings where needed

## Project Overview
Building a voice-first Gmail assistant that enables hands-free email management through natural language voice interactions using Gemini Live API with streaming audio processing, FastAPI backend, and multi-user support.

## Architecture Design

### Modular Structure (Following FastAPI Best Practices)
```
gmail-assistant/
├── app/                      # Main application package
│   ├── main.py               # FastAPI app initialization & lifecycle
│   ├── config.py             # Centralized configuration (Pydantic Settings)
│   ├── auth.py               # Unified authentication (Firebase + OAuth)
│   ├── background_tasks.py   # Background task manager for cleanup
│   ├── api/                  # API route aggregation
│   │   ├── __init__.py
│   │   └── routes.py         # Main router combining all sub-routers
│   ├── routers/              # API endpoints (organized by domain)
│   │   ├── __init__.py       # Router exports
│   │   ├── auth.py           # Firebase login & Gmail OAuth endpoints
│   │   ├── gmail.py          # Gmail operations (read, modify, search)
│   │   ├── voice.py          # Voice interaction endpoints
│   │   ├── websocket.py      # WebSocket streaming endpoint
│   │   └── health.py         # Health check endpoint
│   ├── models/               # Domain models (internal representation)
│   │   ├── __init__.py
│   │   ├── user.py           # User model
│   │   ├── message.py        # Gmail message model
│   │   ├── session.py        # Session model
│   │   └── draft.py          # Draft model
│   ├── schemas/              # Pydantic schemas (API contracts)
│   │   ├── __init__.py       # Schema exports
│   │   ├── auth.py           # Auth request/response schemas
│   │   ├── gmail.py          # Gmail request/response schemas
│   │   ├── voice.py          # Voice request/response schemas
│   │   └── session.py        # Session schemas
│   ├── services/             # Business logic layer
│   │   ├── __init__.py
│   │   ├── firebase_async.py # Async Firebase auth wrapper
│   │   ├── gmail_service.py  # Gmail API client (EXISTING ✅)
│   │   ├── gemini_service.py # Gemini Live API integration
│   │   ├── redis_client.py   # Redis connection & operations
│   │   ├── session_service.py# Session management
│   │   ├── draft_service.py  # Draft management
│   │   └── user_service.py   # User management
│   └── utils/                # Shared utilities
│       ├── logging_config.py # Structured logging setup
│       ├── message_parser.py # Email content parsing
│       └── audio_utils.py    # Audio processing helpers
├── tests/                    # Unit & integration tests
├── requirements.txt          # Dependencies
└── .env                      # Environment variables
```

## Core Components

### 1. Application Initialization (`app/main.py`)
- **create_app()**: Factory function for FastAPI application
- **Startup Events**: Initialize Firebase, Redis, background tasks
- **Shutdown Events**: Cleanup connections and executors
- **Router Registration**: Include all domain routers

### 2. Configuration Management (`app/config.py`)
- **Pydantic Settings**: Type-safe environment variable management
- **Service Configuration**: Firebase, Redis, Gmail, Gemini settings
- **Validation Methods**: Config validation at startup
- **Single Source of Truth**: All settings in one place

### 3. Authentication (`app/auth.py`)
- **Unified Auth Dependencies**: `get_current_user()` for HTTP endpoints
- **WebSocket Auth**: `authenticate_websocket_user()` with query params
- **Firebase Integration**: Token verification with async wrapper
- **OAuth Management**: Gmail OAuth token handling
- **User Creation**: Auto-create users in Redis on first auth

### 4. Routers (`app/routers/`)
- **Domain-Specific Routers**: Each file handles one domain (auth, gmail, voice)
- **Clean Exports**: `__init__.py` exports all routers for easy import
- **Dependency Injection**: Use auth dependencies for protected routes
- **Consistent Patterns**: Standard request/response schemas

### 5. Services (`app/services/`)
- **Business Logic Separation**: All business logic in service layer
- **Async Operations**: Redis, Firebase, external APIs all async
- **Service Pattern**: Each service manages one domain
- **Reusable**: Services used across multiple routers

### 6. Models vs Schemas
- **models/**: Internal domain models (how we store data)
- **schemas/**: API contracts (what we expose to clients)
- **Clear Separation**: Models ≠ Schemas for flexibility

### 7. Background Tasks (`app/background_tasks.py`)
- **Task Manager**: Central manager for all background tasks
- **Graceful Lifecycle**: Start on app startup, stop on shutdown
- **Cleanup Tasks**: Session cleanup, token refresh, etc.
- **Error Handling**: Continue running even on individual task failures

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

## Best Practices (Following auto-translator-server architecture)

### 1. Project Structure
- **app/**: Main package (not src/) for cleaner imports and deployment
- **Flat service layer**: Services directly in `app/services/` without nesting
- **Clear separation**: routers → services → models/schemas
- **Centralized config**: Single `config.py` with Pydantic Settings
- **Clean exports**: Use `__init__.py` to export routers and schemas

### 2. Application Lifecycle
- **Factory pattern**: `create_app()` function for FastAPI initialization
- **Startup events**: Initialize Firebase, connect to Redis, start background tasks
- **Shutdown events**: Cleanup connections, close Redis, cleanup executors
- **Router registration**: Include all domain routers in main app

### 3. Authentication Pattern
- **Unified auth**: Single `get_current_user()` dependency for HTTP endpoints
- **WebSocket auth**: Separate `authenticate_websocket_user()` using query parameters
- **Auto-create users**: Create user records in Redis on first authentication
- **Firebase async wrapper**: Use async wrapper for blocking Firebase SDK calls

### 4. Router Organization
- **Domain-specific**: One router per domain (auth, gmail, voice, websocket, health)
- **Router exports**: `app/routers/__init__.py` exports all routers
- **Central aggregation**: `app/api/routes.py` combines all routers
- **Dependency injection**: Use auth dependencies consistently

### 5. Service Pattern
- **Singleton instances**: Services as global singletons (e.g., `redis_service`)
- **Async operations**: All external I/O operations are async
- **Service initialization**: Connect/initialize in startup events
- **Clean shutdown**: Close connections in shutdown events

### 6. Configuration Management
- **Pydantic Settings**: Use `pydantic_settings.BaseSettings` for type safety
- **Environment variables**: Load from `.env` file and environment
- **Validation methods**: Add custom validation methods in Settings class
- **Single source**: All configuration in `app/config.py`

### 7. Models vs Schemas
- **models/**: Internal domain models (database/Redis representation)
- **schemas/**: Pydantic schemas for API contracts (request/response)
- **Clear separation**: Models and schemas can differ based on needs
- **Schema exports**: Re-export all schemas in `app/schemas/__init__.py`

### 8. Background Tasks
- **Task manager**: Central `BackgroundTaskManager` class
- **Lifecycle management**: Start on app startup, stop on shutdown
- **Graceful cancellation**: Cancel tasks and wait for completion
- **Error resilience**: Continue running even if individual tasks fail

### 9. Logging
- **Centralized setup**: `app/utils/logging_config.py` with `setup_logging()`
- **Call at startup**: Setup logging before anything else in `main.py`
- **Structured logging**: Consistent format across application
- **Appropriate levels**: Use INFO for normal flow, WARNING for issues, ERROR for failures

### 10. Error Handling
- **Consistent exceptions**: Use FastAPI's HTTPException throughout
- **Service-level errors**: Services raise domain-specific exceptions
- **Router conversion**: Routers catch and convert to appropriate HTTP responses
- **Proper logging**: Log errors with context at appropriate levels

### 11. Dependency Injection Best Practices
- **Auth dependencies**: Always use `Depends(get_current_user)` for protected routes
- **Service singletons**: Import services directly, don't inject
- **Settings access**: Import `settings` directly where needed
- **WebSocket limitations**: Use Query parameters for WebSocket auth (not Depends)