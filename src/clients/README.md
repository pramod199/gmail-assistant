# Gmail Voice Assistant - PyAudio Client

A streaming voice client for testing the Gmail Voice Assistant server.

## Setup

### 1. Install Dependencies

```bash
pip install -r ../../requirements.txt
```

### 2. Configure Firebase Web API Key

Get your Firebase Web API Key:
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Click the gear icon (⚙️) → Project Settings
4. Under "General" tab, scroll to "Your apps"
5. Copy the "Web API Key"

**Option A: Using environment variable (recommended)**
```bash
export FIREBASE_WEB_API_KEY="your_api_key_here"
```

**Option B: Using firebase_config.py**
```bash
cp firebase_config.py firebase_config.py
# Edit firebase_config.py and set FIREBASE_API_KEY
```

### 3. Ensure Server is Running

Make sure the Gmail Assistant server is running:
```bash
cd ../..
python app.py
```

## Usage

### Run the Client

```bash
python pyaudio_client.py
```

### Authentication Flow

1. **Enter your Firebase credentials:**
   - Email: Your Firebase user email
   - Password: Your Firebase user password

2. **The client will:**
   - Authenticate with Firebase
   - Get an ID token
   - Create a voice session via REST API
   - Connect to the WebSocket
   - Start streaming audio

3. **Start speaking:**
   - "Read my unread emails"
   - "Next message"
   - "Summarize this message"
   - "Mark as read"
   - "Draft a reply saying thanks"

4. **Exit:**
   - Press `Ctrl+C` to quit

## How It Works

### 1. Firebase Authentication (App-Level Auth)
   - Client signs in with email/password
   - Firebase returns an ID token
   - Token is sent to server with each API request
   - Server validates token with Firebase Admin SDK
   - User is authenticated for app access

### 2. Gmail OAuth Authorization (Gmail-Level Auth)
   - **First Time Setup:**
     - Client calls `POST /api/sessions`
     - Server checks if user has Gmail OAuth credentials
     - If not: returns `gmail_auth_url`
     - Client displays URL for user to authorize Gmail access
     - User clicks URL, grants permissions via Google OAuth
     - Server stores refresh token in Redis

   - **Subsequent Uses:**
     - Server checks for stored credentials
     - If expired: automatically refreshes using refresh token
     - If refresh fails: requires re-authorization
     - Client detects and prompts for new authorization

### 3. Session Management
   - Client calls `POST /api/sessions` with Firebase auth token
   - Server creates a voice session
   - Client connects WebSocket with session_id
   - Server validates session exists and is active

### 4. Audio Streaming
   - Bidirectional audio streaming
   - Real-time voice processing with Gemini Live API
   - Gmail operations via function calling

## Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT STARTUP                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Firebase Sign In              │
         │  (Email/Password)              │
         │  → Get ID Token                │
         └────────────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  POST /api/sessions            │
         │  (with Firebase token)         │
         └────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
    ┌───────────────────┐   ┌──────────────────┐
    │ Gmail Authorized  │   │ Gmail NOT Auth   │
    └───────────────────┘   └──────────────────┘
                │                   │
                │                   ▼
                │       ┌──────────────────────┐
                │       │ Display OAuth URL    │
                │       │ User authorizes via  │
                │       │ browser              │
                │       └──────────────────────┘
                │                   │
                │                   ▼
                │       ┌──────────────────────┐
                │       │ Verify Authorization │
                │       │ GET /auth/gmail/     │
                │       │     status           │
                │       └──────────────────────┘
                │                   │
                └───────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │  Connect WebSocket             │
         │  Start Voice Streaming         │
         └────────────────────────────────┘
```

## Token Management

### Firebase Token (App Authentication)
- **Duration:** 1 hour
- **Refresh:** Client must re-authenticate when expired
- **Storage:** Client memory only
- **Purpose:** Authenticate user for app access

### Gmail OAuth Token (Gmail Access)
- **Access Token Duration:** 1 hour
- **Refresh Token Duration:** Indefinite (until revoked)
- **Auto-Refresh:** Server automatically refreshes access token
- **Storage:** Refresh token stored in Redis (30 days TTL)
- **Re-authorization Required When:**
  - Refresh token expires
  - User revokes access
  - Credentials deleted from Redis
  - Token refresh fails

## Troubleshooting

### "FIREBASE_API_KEY not configured"
- Set the environment variable or update firebase_config.py

### "EMAIL_NOT_FOUND"
- Create a Firebase user first via Firebase Console
- Or implement signup functionality

### "Invalid Firebase token"
- Check that server has correct Firebase service account configured
- Ensure FIREBASE_SERVICE_ACCOUNT_PATH is set in server .env

### "Failed to create session: 401"
- Check that Firebase token is being sent correctly
- Verify server Firebase configuration
