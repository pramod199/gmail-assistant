# Gmail Voice Assistant

A voice-first Gmail assistant that enables hands-free email management through natural language voice interactions using Gemini Live API with streaming audio processing, FastAPI backend, and multi-user support.

## Features

🎙️ **Voice-First Interface**
- Real-time streaming voice processing via WebSocket
- Natural conversation with Gmail assistant
- Audio isolation to prevent feedback loops
- Multi-user support with session isolation

📧 **Gmail Operations**
- Read emails with natural voice commands
- Navigate through messages (next, previous, first, last)
- Smart message filtering and search
- Mark messages as read, starred, archived
- Create and send email drafts

🧠 **AI-Powered**
- Gemini Live API integration with function calling
- Natural language understanding for complex queries
- Voice-optimized response formatting
- Smart pagination and session management

🔐 **Secure & Scalable**
- Firebase Authentication with Gmail OAuth
- Redis-based session management
- Multi-user isolation
- Secure token management

## Architecture

```
Voice Client → WebSocket → FastAPI → Gemini Live API → Gmail API
                    ↓
               Redis Session Store
```

### Components
- **FastAPI Backend**: WebSocket + REST endpoints with Firebase auth
- **Gemini Live API**: Streaming voice processing with function calling
- **Gmail API**: Unified email operations (read, modify, drafts, search)
- **Redis**: Session management and user state
- **PyAudio Client**: Test client with audio isolation

## Quick Start

### Prerequisites
- Python 3.11+
- Redis server
- Google Cloud Project (for Gmail API)
- Firebase Project (for authentication)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Redis Server

```bash
# Option A: Using Docker (Recommended)
docker-compose up redis -d

# Option B: Local Redis
redis-server
```

### 3. Setup Firebase & Gmail API

**Firebase Setup:**
1. Create Firebase project at https://console.firebase.google.com
2. Generate service account key
3. Save as `firebase-service-account.json`

**Gmail API Setup:**
1. Create Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Save as `credentials.json`

### 4. Generate Test Token

```bash
python create_test_token.py
```

This will create a Firebase token for testing.

### 5. Start Server

```bash
python app.py
```

Server will run on `http://localhost:8000`

### 6. Test Voice Interface

```bash
python src/clients/pyaudio_client.py
```

Enter your Firebase token and start speaking!

## Usage Examples

### Voice Commands

**Reading Emails:**
- "Read my unread emails"
- "Read messages from John"  
- "Show me important emails from today"
- "Read the latest message about the meeting"

**Navigation:**
- "Next message"
- "Previous message" 
- "Go to first message"
- "Read full message"

**Message Actions:**
- "Mark this as read"
- "Summarize this message"
- "Star this message"

**Drafting:**
- "Draft a reply saying I'll be there"
- "Compose email to john@example.com"
- "Send the draft"

### REST API Endpoints

**Base URL:** `http://localhost:8000`

**Authentication:**
All endpoints require Firebase token:
```
Authorization: Bearer <firebase_id_token>
```

**Gmail Endpoints:**
```
GET  /api/gmail/messages                    # Get messages
GET  /api/gmail/messages/{message_id}       # Get specific message  
POST /api/gmail/messages/{id}/mark-read     # Mark as read
POST /api/gmail/process                     # Natural language processing
```

**WebSocket Endpoint:**
```
WS   /api/voice/voice?token=<firebase_token> # Voice streaming
```

**Message Flow:**
```json
// Client -> Server (audio chunk)
{
    "type": "audio_chunk",
    "data": "base64_encoded_audio",
    "audio_format": {
        "sample_rate": 16000,
        "channels": 1,
        "mime_type": "audio/pcm;rate=16000"
    }
}

// Server -> Client (audio response)
{
    "type": "audio_response", 
    "data": "base64_encoded_audio",
    "session_state": {
        "current_index": 0,
        "total_messages": 5,
        "has_more": false
    }
}
```

## Development

### Project Structure

```
gmail-assistant/
├── src/
│   ├── api/                     # FastAPI application
│   │   ├── controllers/         # REST & WebSocket controllers
│   │   ├── middleware/          # Firebase auth middleware
│   │   └── websocket/           # Voice WebSocket handler
│   ├── core/
│   │   ├── auth/                # Firebase + Gmail OAuth
│   │   ├── gmail_client/        # Gmail API integration  
│   │   ├── voice/               # Gemini Live API + function calling
│   │   └── session/             # Redis session management
│   ├── clients/
│   │   └── pyaudio_client.py    # Test client
│   └── config/                  # Configuration
├── live_audio_example/          # Gemini Live API examples
├── create_test_token.py         # Token generation utility
├── app.py                       # FastAPI server entry point
└── requirements.txt             # Dependencies
```

### Key Technologies

- **FastAPI**: Modern web framework with WebSocket support
- **Gemini Live API**: Real-time voice processing with function calling
- **Firebase Auth**: User authentication and session management  
- **Gmail API**: Email operations with OAuth 2.0
- **Redis**: Session state and user data storage
- **PyAudio**: Audio recording/playback for test client

### Environment Variables

Create `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
GMAIL_CREDENTIALS_FILE=credentials.json
```

### Multi-User Architecture

Each user gets isolated:
- **WebSocket connection** with separate authentication
- **Gmail credentials** and API access  
- **Session state** in Redis (navigation, drafts)
- **Gemini Live session** for voice processing

**Redis Data Structure:**
```redis
# Single hash per data type for all users
user_tokens = {
  "firebase_uid_1": {"gmail_access_token": "...", "gmail_refresh_token": "..."},
  "firebase_uid_2": {"gmail_access_token": "...", "gmail_refresh_token": "..."}
}

user_sessions = {
  "firebase_uid_1": {"current_message_id": "...", "message_queue": [...]},  
  "firebase_uid_2": {"current_message_id": "...", "message_queue": [...]}
}
```

## Testing

### Local Testing - Complete Walkthrough

**Prerequisites Check:**
```bash
# 1. Verify Python version
python --version  # Should be 3.11+

# 2. Check Redis is running
redis-cli ping     # Should return PONG

# 3. Verify required files exist
ls firebase-service-account.json credentials.json
```

**Step 1: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 2: Generate Test Firebase Token**
```bash
python create_test_token.py
```
Save the generated token - you'll need it for testing.

**Step 3: Start FastAPI Server** 
```bash
python app.py
```
Server should start on `http://localhost:8000`. Verify with:
```bash
curl http://localhost:8000/health
```

**Step 4: Authorize Gmail Access**
```bash
# Get your Firebase token from Step 2, then:
curl -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
     http://localhost:8000/api/auth/gmail/status
```
If `is_authorized: false`, visit the returned `auth_url` in browser to complete OAuth.

**Step 5: Test Voice Interface**
```bash
# In a new terminal:
python src/clients/pyaudio_client.py
```
- Enter your Firebase token when prompted
- Wait for "Connected to voice assistant!"
- Start speaking: "Read my unread emails"

### Voice Testing Flow

1. **Generate token**: `python create_test_token.py`
2. **Start server**: `python app.py`
3. **Start client**: `python src/clients/pyaudio_client.py`
4. **Speak naturally**: "Read my unread emails"
5. **Navigate**: "Next message", "Mark as read"

### REST API Testing

Use Postman collection: `Gmail_Assistant_API.postman_collection.json`

Or curl:
```bash
# Get messages
curl -H "Authorization: Bearer $FIREBASE_TOKEN" \
     http://localhost:8000/api/gmail/messages

# Process natural language
curl -X POST -H "Authorization: Bearer $FIREBASE_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"query": "show me unread emails from john"}' \
     http://localhost:8000/api/gmail/process
```

## Deployment

### Docker Deployment

```bash
# Build and run
docker-compose up --build

# Production with Redis
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Setup

- **Development**: Local Redis, Firebase emulator
- **Production**: Redis Cloud, Firebase production project

## API Documentation

Once server is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

**Common Issues:**

1. **Firebase Token Invalid**
   - Regenerate: `python create_test_token.py`
   - Check `firebase-service-account.json` exists

2. **Gmail Authorization Required**  
   - Visit `/api/auth/gmail/status` to get auth URL
   - Complete OAuth flow in browser

3. **Redis Connection Failed**
   - Check Redis is running: `redis-cli ping`
   - Verify connection settings in config

4. **Audio Issues**
   - Install PyAudio: `pip install pyaudio`  
   - Check microphone permissions
   - Try different audio devices

5. **WebSocket Connection Failed**
   - Check server is running on port 8000
   - Verify Firebase token is valid
   - Check browser/client WebSocket support

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check troubleshooting section above
2. Review API docs at `/docs` endpoint  
3. Open GitHub issue with detailed description
4. Include logs and error messages

---

**Built with ❤️ using Gemini Live API, FastAPI, and modern Python**