# Gmail Voice Assistant - Complete API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Authentication Flow](#authentication-flow)
3. [Gmail Authorization Flow](#gmail-authorization-flow)
4. [Application Flow](#application-flow)
5. [WebSocket Flow](#websocket-flow)
6. [API Endpoints](#api-endpoints)
7. [User Configuration](#user-configuration)
8. [Error Handling](#error-handling)
9. [Code Examples](#code-examples)

---

## Overview

The Gmail Voice Assistant is a voice-first email management system with three distinct authorization layers:

1. **Firebase Authentication** - App-level user authentication
2. **Gmail OAuth 2.0** - Gmail API access authorization
3. **Session Management** - Voice session lifecycle

**Base URL:** `http://localhost:8000` (development)

**Key Features:**
- Real-time voice streaming with Gemini Live API
- Server-side Voice Activity Detection (VAD) for interruption handling
- User-configurable email behavior (auto mark as read, auto send drafts)
- Multi-user session management
- Automatic token refresh

---

## Authentication Flow

### Step 1: Sign In with Firebase

**Client-Side Firebase Authentication:**

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 1. POST email/password to Firebase
       ├──────────────────────────────────────────┐
       │                                          │
       │                                    ┌─────▼─────┐
       │                                    │ Firebase  │
       │                                    │   Auth    │
       │                                    └─────┬─────┘
       │                                          │
       │ 2. Receive Firebase ID Token (JWT)      │
       │◄─────────────────────────────────────────┘
       │
       │ 3. Include token in all API requests
       │    Authorization: Bearer <firebase_token>
       │
```

**Endpoint:** Firebase REST API (not our server)
```
POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<FIREBASE_WEB_API_KEY>
```

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password",
  "returnSecureToken": true
}
```

**Response:**
```json
{
  "idToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ij...",
  "email": "user@example.com",
  "refreshToken": "...",
  "expiresIn": "3600",
  "localId": "firebase_user_id_here"
}
```

### Step 2: Server Validates Token & Creates User

**What Happens on First Request:**

```
┌─────────────┐                     ┌─────────────┐                  ┌─────────────┐
│   Client    │                     │   Server    │                  │   Redis     │
└──────┬──────┘                     └──────┬──────┘                  └──────┬──────┘
       │                                   │                                │
       │ POST /api/sessions                │                                │
       │ Authorization: Bearer <token>     │                                │
       ├──────────────────────────────────>│                                │
       │                                   │                                │
       │                                   │ 1. Validate Firebase token     │
       │                                   │    with Firebase Admin SDK     │
       │                                   │                                │
       │                                   │ 2. Extract user_id & email     │
       │                                   │                                │
       │                                   │ 3. Check if user exists        │
       │                                   ├───────────────────────────────>│
       │                                   │                                │
       │                                   │ 4. User NOT found              │
       │                                   │◄───────────────────────────────┤
       │                                   │                                │
       │                                   │ 5. CREATE new user record      │
       │                                   │    - user_id, email            │
       │                                   │    - created_at, login_count=1 │
       │                                   ├───────────────────────────────>│
       │                                   │                                │
       │                                   │ 6. User created ✓              │
       │                                   │◄───────────────────────────────┤
       │                                   │                                │
       │ Session response                  │                                │
       │◄──────────────────────────────────┤                                │
```

**Subsequent Requests:**
- Server finds existing user
- Updates `last_login` timestamp
- Increments `login_count`
- Continues processing request

**Token Requirements:**
- **Format:** `Authorization: Bearer <firebase_id_token>`
- **Duration:** 1 hour (client must re-authenticate when expired)
- **All Protected Endpoints:** Require this header

---

## Gmail Authorization Flow

### Why Separate Gmail Authorization?

Firebase auth = **Who you are** (identifies the user)
Gmail OAuth = **What you can access** (grants Gmail permissions)

### Step 1: Check Gmail Authorization Status

```
┌─────────────┐                     ┌─────────────┐                  ┌─────────────┐
│   Client    │                     │   Server    │                  │   Redis     │
└──────┬──────┘                     └──────┬──────┘                  └──────┬──────┘
       │                                   │                                │
       │ POST /api/sessions                │                                │
       │ Authorization: Bearer <token>     │                                │
       ├──────────────────────────────────>│                                │
       │                                   │                                │
       │                                   │ Check Gmail credentials        │
       │                                   ├───────────────────────────────>│
       │                                   │                                │
       │                                   │ NOT FOUND                      │
       │                                   │◄───────────────────────────────┤
       │                                   │                                │
       │                                   │ Generate OAuth URL             │
       │                                   │                                │
       │ {                                 │                                │
       │   "session_id": "uuid",           │                                │
       │   "gmail_authorized": false,      │                                │
       │   "requires_gmail_auth": true,    │                                │
       │   "gmail_auth_url": "https://..." │                                │
       │ }                                 │                                │
       │◄──────────────────────────────────┤                                │
```

### Step 2: User Authorizes Gmail Access

```
┌─────────────┐                     ┌─────────────┐                  ┌─────────────┐
│   Client    │                     │   Server    │                  │   Google    │
└──────┬──────┘                     └──────┬──────┘                  └──────┬──────┘
       │                                   │                                │
       │ 1. Display gmail_auth_url         │                                │
       │    to user                        │                                │
       │                                   │                                │
       │ 2. User opens URL in browser      │                                │
       ├────────────────────────────────────────────────────────────────────>│
       │                                   │                                │
       │                                   │          [User grants          │
       │                                   │           permissions]         │
       │                                   │                                │
       │                                   │ 3. Google redirects to         │
       │                                   │    /api/auth/gmail/callback    │
       │                                   │    with auth code              │
       │                                   │◄───────────────────────────────┤
       │                                   │                                │
       │                                   │ 4. Exchange code for tokens    │
       │                                   ├───────────────────────────────>│
       │                                   │                                │
       │                                   │ 5. Access + Refresh tokens     │
       │                                   │◄───────────────────────────────┤
       │                                   │                                │
       │                                   │ 6. Store refresh token         │
       │                                   │    in Redis (30 days TTL)      │
       │                                   ├──────────────────>Redis        │
       │                                   │                                │
       │ 7. Client verifies authorization  │                                │
       │    GET /api/auth/gmail/status     │                                │
       ├──────────────────────────────────>│                                │
       │                                   │                                │
       │ { "is_authorized": true }         │                                │
       │◄──────────────────────────────────┤                                │
```

### Step 3: Automatic Token Refresh

```
┌─────────────┐                     ┌─────────────┐                  ┌─────────────┐
│   Client    │                     │   Server    │                  │   Redis     │
└──────┬──────┘                     └──────┬──────┘                  └──────┬──────┘
       │                                   │                                │
       │ Gmail operation (e.g. read mail)  │                                │
       ├──────────────────────────────────>│                                │
       │                                   │                                │
       │                                   │ Get credentials                │
       │                                   ├───────────────────────────────>│
       │                                   │                                │
       │                                   │ Credentials (access token)     │
       │                                   │◄───────────────────────────────┤
       │                                   │                                │
       │                                   │ Check if expired               │
       │                                   │                                │
       │                                   │ IF EXPIRED:                    │
       │                                   │ - Use refresh token            │
       │                                   │ - Get new access token         │
       │                                   │ - Update Redis                 │
       │                                   │                                │
       │                                   │ IF REFRESH FAILS:              │
       │                                   │ - Delete credentials           │
       │                                   │ - Return auth error            │
       │                                   │                                │
       │ Success / Need re-auth            │                                │
       │◄──────────────────────────────────┤                                │
```

---

## Application Flow

### Complete First-Time User Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    1. FIREBASE AUTHENTICATION                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  User provides email/password
                              │
                              ▼
                  Client → Firebase REST API
                              │
                              ▼
                  Receives Firebase ID Token
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    2. CREATE VOICE SESSION                       │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
          POST /api/sessions (with Firebase token)
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Server Side:         │
                  │  1. Validate token    │
                  │  2. Create user (1st) │
                  │  3. Check Gmail auth  │
                  │  4. Create session    │
                  └───────────────────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
                ▼                            ▼
     Gmail Authorized              Gmail NOT Authorized
                │                            │
                │                            ▼
                │              ┌──────────────────────────┐
                │              │ 3. GMAIL AUTHORIZATION   │
                │              └──────────────────────────┘
                │                            │
                │                            ▼
                │              Display gmail_auth_url to user
                │                            │
                │                            ▼
                │              User opens URL → Google OAuth
                │                            │
                │                            ▼
                │              User grants permissions
                │                            │
                │                            ▼
                │              Google → /callback with code
                │                            │
                │                            ▼
                │              Server exchanges code for tokens
                │                            │
                │                            ▼
                │              Store refresh token in Redis
                │                            │
                │                            ▼
                │              Client verifies: GET /auth/gmail/status
                │                            │
                └────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    4. CONNECT WEBSOCKET                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    WS /api/voice/voice?session_id=X&firebase_user_id=Y
                              │
                              ▼
                  Server validates session
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    5. START VOICE STREAMING                      │
└──────────────────────────────────────────────────────────────────┘
```

### Returning User Flow (Simplified)

```
1. Firebase Sign In → Get ID Token
2. POST /api/sessions → Server finds user, Gmail already authorized
3. Connect WebSocket → Start streaming
```

---

## WebSocket Flow

### Connection Establishment

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ 1. Create session via REST                      │
       │    POST /api/sessions                           │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │ 2. Receive session_id                           │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ 3. Connect WebSocket                            │
       │    ws://host/api/voice/voice?                   │
       │      session_id=X&firebase_user_id=Y            │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Validate session
       │                                                  │ Check session.active
       │                                                  │ Load Gmail service
       │                                                  │
       │ 4. {"type": "connected"}                        │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ 5. {"type": "start_voice_session"}              │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Initialize Gemini
       │                                                  │ Live API session
       │                                                  │
       │ 6. {"type": "voice_session_started"}            │
       │◄────────────────────────────────────────────────┤
```

### Voice Streaming Cycle

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
│  (PyAudio)  │                                    │  (Gemini)   │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ ┌──────────────────────────────────────┐        │
       │ │  AUDIO INPUT LOOP                    │        │
       │ └──────────────────────────────────────┘        │
       │                                                  │
       │ Record from microphone (16kHz PCM)              │
       │ Buffer for 1.5 seconds                          │
       │                                                  │
       │ {"type": "audio_chunk",                         │
       │  "data": "base64_audio",                        │
       │  "audio_format": {...}}                         │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Send to Gemini
       │                                                  │ Live API
       │                                                  │
       │                                                  │ Gemini processes
       │                                                  │ speech-to-text
       │                                                  │
       │                                                  │ Gemini determines
       │                                                  │ intent & function
       │                                                  │
       │ ┌──────────────────────────────────────┐        │
       │ │  FUNCTION EXECUTION                  │        │
       │ └──────────────────────────────────────┘        │
       │                                                  │
       │                                                  │ Execute Gmail
       │                                                  │ function (e.g.
       │                                                  │ read_messages)
       │                                                  │
       │ {"type": "function_executed",                   │
       │  "function_name": "read_messages",              │
       │  "result": {...}}                               │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ ┌──────────────────────────────────────┐        │
       │ │  AUDIO OUTPUT LOOP                   │        │
       │ └──────────────────────────────────────┘        │
       │                                                  │
       │                                                  │ Gemini generates
       │                                                  │ speech response
       │                                                  │
       │ {"type": "audio_response",                      │
       │  "data": "base64_audio"}                        │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ Decode & play audio (24kHz PCM)                 │
       │                                                  │
       │ ┌──────────────────────────────────────┐        │
       │ │  TEXT ALTERNATIVE                    │        │
       │ └──────────────────────────────────────┘        │
       │                                                  │
       │ {"type": "text_response",                       │
       │  "text": "You have 5 unread emails..."}         │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ Display text (optional)                         │
```

### Session State Updates

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ User says: "Read my unread emails"              │
       │                                                  │
       │ [Audio streamed to server]                      │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Gemini: read_messages()
       │                                                  │ Fetch emails from Gmail
       │                                                  │ Store in Redis session
       │                                                  │
       │ {"type": "session_state",                       │
       │  "current_index": 0,                            │
       │  "total_messages": 5,                           │
       │  "has_more": false}                             │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ User says: "Next message"                       │
       │                                                  │
       │ [Audio streamed to server]                      │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Gemini: navigate_messages()
       │                                                  │ Get next from Redis
       │                                                  │
       │ {"type": "session_state",                       │
       │  "current_index": 1,                            │
       │  "total_messages": 5,                           │
       │  "has_more": false}                             │
       │◄────────────────────────────────────────────────┤
```

### Server-Side VAD Interruption Handling

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ ┌──────────────────────────────────────┐        │
       │ │  USER INTERRUPTS ASSISTANT           │        │
       │ └──────────────────────────────────────┘        │
       │                                                  │
       │ Assistant is speaking...                        │
       │ Playing audio response                          │
       │                                                  │
       │ User starts speaking (interruption)             │
       │                                                  │
       │ Continue sending audio chunks                   │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Gemini Live API
       │                                                  │ VAD detects user
       │                                                  │ speaking
       │                                                  │
       │                                                  │ server_content.
       │                                                  │ interrupted = true
       │                                                  │
       │ {"type": "stop_audio",                          │
       │  "message": "User interrupted"}                 │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ IMMEDIATELY:                                    │
       │ - Stop audio playback                           │
       │ - Clear audio queue                             │
       │ - Ready for new response                        │
       │                                                  │
       │                                                  │ Process new
       │                                                  │ user input
       │                                                  │
       │ {"type": "audio_response",                      │
       │  "data": "new_response_audio"}                  │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ Play new response                               │
```

**Key Points:**
- **Server-side detection:** Gemini Live API's VAD detects interruptions automatically
- **No client-side monitoring:** Client doesn't need to monitor audio levels
- **Immediate response:** Client receives `stop_audio` message and clears playback queue
- **Natural conversation:** Enables barge-in/interruption for natural voice interaction

### Error Handling in WebSocket

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ Gmail operation requested                       │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Check credentials
       │                                                  │ Token expired
       │                                                  │ Refresh fails
       │                                                  │
       │ {"type": "error",                               │
       │  "message": "Gmail auth required",              │
       │  "action_required": "gmail_auth",               │
       │  "auth_url": "https://..."}                     │
       │◄────────────────────────────────────────────────┤
       │                                                  │
       │ Display error to user                           │
       │ Provide auth URL                                │
       │ Close WebSocket                                 │
       │ User re-authorizes Gmail                        │
       │ Reconnect with new session                      │
```

### Connection Cleanup

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ User exits / Ctrl+C                             │
       │                                                  │
       │ Close WebSocket                                 │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Mark session.active=false
       │                                                  │ Update Redis
       │                                                  │ Close Gemini session
       │                                                  │
       │ DELETE /api/sessions/{session_id}               │
       ├────────────────────────────────────────────────>│
       │                                                  │
       │                                                  │ Delete session
       │                                                  │ from Redis
       │                                                  │
       │ 204 No Content                                  │
       │◄────────────────────────────────────────────────┤
```

---

## API Endpoints

### Authentication Endpoints

#### 1. Check Gmail Authorization Status

```http
GET /api/auth/gmail/status
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "is_authorized": false,
  "user_id": "firebase_uid",
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

#### 2. Start Gmail OAuth Flow

```http
GET /api/auth/gmail/authorize
Authorization: Bearer <firebase_token>
```

**Response:** `302 Redirect` to Google OAuth

#### 3. OAuth Callback (Public)

```http
GET /api/auth/gmail/callback?code=xxx&state=yyy
```

**Response:**
```json
{
  "success": true,
  "message": "Gmail authorization successful",
  "user_id": "firebase_uid",
  "next_step": "You can now use Gmail API endpoints"
}
```

#### 4. Revoke Gmail Access

```http
DELETE /api/auth/gmail/revoke
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "message": "Gmail access revoked successfully"
}
```

---

### User Endpoints

#### 1. Get Current User Profile

```http
GET /api/users/me
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "user_id": "firebase_uid",
  "email": "user@example.com",
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T14:30:00Z",
  "last_login": "2025-01-10T14:30:00Z",
  "login_count": 5
}
```

#### 2. Get User Statistics

```http
GET /api/users/stats
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "total_users": 42
}
```

#### 3. Delete User Record

```http
DELETE /api/users/me
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "message": "Local user record deleted successfully",
  "user_id": "firebase_uid",
  "note": "Firebase account remains active. User will be recreated on next login."
}
```

---

### Session Endpoints

#### 1. Create Voice Session

```http
POST /api/sessions
Authorization: Bearer <firebase_token>
Content-Type: application/json

{}
```

**Response (Gmail Authorized):**
```json
{
  "session_id": "c6093ee2-f30b-43b3-93f4-e520bb59cc2f",
  "user_id": "firebase_uid",
  "active": true,
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:00:00Z",
  "gmail_authorized": true,
  "requires_gmail_auth": false
}
```

**Response (Gmail NOT Authorized):**
```json
{
  "session_id": "c6093ee2-f30b-43b3-93f4-e520bb59cc2f",
  "user_id": "firebase_uid",
  "active": true,
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:00:00Z",
  "gmail_authorized": false,
  "gmail_auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "requires_gmail_auth": true
}
```

#### 2. List Sessions

```http
GET /api/sessions
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid-1",
      "user_id": "firebase_uid",
      "active": true,
      "created_at": "2025-01-10T12:00:00Z",
      "updated_at": "2025-01-10T12:00:00Z",
      "gmail_authorized": true,
      "requires_gmail_auth": false
    }
  ],
  "total": 1,
  "active_count": 1
}
```

#### 3. Get Session Details

```http
GET /api/sessions/{session_id}
Authorization: Bearer <firebase_token>
```

**Response:** Same as individual session object

#### 4. Delete Session

```http
DELETE /api/sessions/{session_id}
Authorization: Bearer <firebase_token>
```

**Response:** `204 No Content`

---

### WebSocket Endpoint

#### Connect to Voice Stream

```
ws://localhost:8000/api/voice/voice?session_id=<id>&firebase_user_id=<uid>
```

**Client → Server Messages:**

**Control Messages (JSON text):**
```json
{
  "type": "start_voice_session"
}
```

```json
{
  "type": "end_voice_session"
}
```

**Audio Data (Raw Binary):**
```
Send raw PCM16 audio bytes directly via WebSocket binary frames
- Format: 16-bit signed integers (little-endian)
- Sample Rate: 16000 Hz
- Channels: 1 (mono)
- No base64 encoding - send raw bytes

Web Audio API Conversion Example:
const pcm16 = new Int16Array(float32Array.length);
for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
}
websocket.send(pcm16.buffer);
```

**Server → Client Messages:**

```json
{
  "type": "connected",
  "message": "WebSocket connected",
  "user_id": "firebase_uid"
}
```

```json
{
  "type": "voice_session_started",
  "message": "Voice session started successfully"
}
```

**Audio Response (Raw Binary):**
```
Raw PCM16 audio bytes sent via WebSocket binary frames
- Format: 16-bit signed integers (little-endian)
- Sample Rate: 24000 Hz (Gemini Live API default output)
- Channels: 1 (mono)
- No base64 encoding - raw bytes
```

```json
{
  "type": "text_response",
  "text": "You have 5 unread emails from..."
}
```

```json
{
  "type": "function_executed",
  "function_name": "read_messages",
  "result": {
    "count": 5,
    "current": 0
  }
}
```

```json
{
  "type": "session_state",
  "current_index": 0,
  "total_messages": 5,
  "has_more": false
}
```

```json
{
  "type": "stop_audio",
  "message": "User interrupted - clear audio queue"
}
```
**Action Required:** Immediately stop audio playback and clear audio queue

```json
{
  "type": "error",
  "message": "Gmail authorization required",
  "action_required": "gmail_auth",
  "auth_url": "/api/auth/gmail/authorize"
}
```

---

## User Configuration

User configuration allows customization of email handling behavior for each user.

### Configuration Options

#### auto_mark_as_read (boolean)
- **Default:** `true`
- **Description:** Automatically mark emails as read when they are read aloud
- **When enabled:** Emails are marked as read immediately after reading
- **When disabled:** Emails remain unread unless explicitly marked

#### auto_send_drafts (boolean)
- **Default:** `false`
- **Description:** Automatically send draft emails immediately vs saving to Gmail drafts
- **When enabled:** Draft emails are sent immediately upon creation
- **When disabled:** Draft emails are saved to Gmail drafts folder for review

### Configuration Endpoints

#### 1. Get User Configuration

```http
GET /api/config/user/config
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "auto_mark_as_read": true,
  "auto_send_drafts": false,
  "created_at": 1736510400,
  "updated_at": 1736510400
}
```

#### 2. Update User Configuration

```http
PUT /api/config/user/config
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "auto_mark_as_read": false,
  "auto_send_drafts": true
}
```

**Request Body:** (all fields optional - only provide fields to update)

**Response:**
```json
{
  "auto_mark_as_read": false,
  "auto_send_drafts": true,
  "created_at": 1736510400,
  "updated_at": 1736514000
}
```

**Validation:**
- Both fields must be boolean values
- At least one field must be provided
- Invalid field names or types return 400 error

#### 3. Get Specific Configuration Value

```http
GET /api/config/user/config/{config_key}
Authorization: Bearer <firebase_token>
```

**Valid config_key values:**
- `auto_mark_as_read`
- `auto_send_drafts`

**Response:**
```json
{
  "key": "auto_mark_as_read",
  "value": true,
  "user_id": "firebase_uid"
}
```

#### 4. Delete User Configuration

```http
DELETE /api/config/user/config
Authorization: Bearer <firebase_token>
```

**Response:**
```json
{
  "message": "User configuration deleted successfully",
  "user_id": "firebase_uid",
  "note": "Default configuration values will be used going forward"
}
```

**Effect:** User reverts to default configuration values

---

## Error Handling

### HTTP Errors

**401 Unauthorized - Missing Token:**
```json
{
  "detail": "Authorization header missing"
}
```

**401 Unauthorized - Invalid Token:**
```json
{
  "detail": "Invalid Firebase ID token: ..."
}
```

**403 Forbidden - Not Your Resource:**
```json
{
  "detail": "Not authorized to access this session"
}
```

**404 Not Found:**
```json
{
  "detail": "Session not found"
}
```

**429 Too Many Requests:**
```json
{
  "error": "too_many_sessions",
  "message": "Maximum concurrent sessions limit (3) reached",
  "active_sessions": 3,
  "max_allowed": 3
}
```

### WebSocket Errors

**Invalid Session:**
```
Close Code: 4003
Reason: "Invalid session"
```

**Gmail Not Authorized:**
```json
{
  "type": "error",
  "message": "Gmail authorization required. Please authorize Gmail access first.",
  "action_required": "gmail_auth",
  "auth_url": "/api/auth/gmail/authorize",
  "user_id": "firebase_uid"
}
```

---

## Code Examples

### Python Client Example

```python
import asyncio
import aiohttp
import websockets
import base64

# 1. Firebase Authentication
async def firebase_sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "email": email,
            "password": password,
            "returnSecureToken": True
        }) as response:
            data = await response.json()
            return data["idToken"], data["localId"]

# 2. Create Session
async def create_session(firebase_token):
    headers = {
        "Authorization": f"Bearer {firebase_token}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/api/sessions",
            json={},
            headers=headers
        ) as response:
            return await response.json()

# 3. Handle Gmail Auth (if needed)
async def handle_gmail_auth(session_data, firebase_token):
    if session_data["requires_gmail_auth"]:
        print(f"Please open: {session_data['gmail_auth_url']}")
        input("Press Enter after authorizing...")

        # Verify
        headers = {"Authorization": f"Bearer {firebase_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:8000/api/auth/gmail/status",
                headers=headers
            ) as response:
                status = await response.json()
                return status["is_authorized"]
    return True

# 4. Connect WebSocket
async def connect_websocket(session_id, user_id):
    url = f"ws://localhost:8000/api/voice/voice?session_id={session_id}&firebase_user_id={user_id}"

    async with websockets.connect(url) as websocket:
        # Start session
        await websocket.send(json.dumps({"type": "start_voice_session"}))

        # Listen for messages
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data['type']}")

            if data["type"] == "audio_response":
                audio_data = base64.b64decode(data["data"])
                # Play audio...

            elif data["type"] == "text_response":
                print(f"Assistant: {data['text']}")

# Main flow
async def main():
    # 1. Sign in
    token, user_id = await firebase_sign_in("user@example.com", "password")

    # 2. Create session
    session = await create_session(token)

    # 3. Handle Gmail auth if needed
    if not await handle_gmail_auth(session, token):
        print("Gmail authorization failed")
        return

    # 4. Connect and stream
    await connect_websocket(session["session_id"], user_id)

asyncio.run(main())
```

### JavaScript/TypeScript Example

```typescript
// 1. Firebase Authentication
async function firebaseSignIn(email: string, password: string) {
  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_API_KEY}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        returnSecureToken: true
      })
    }
  );

  const data = await response.json();
  return { token: data.idToken, userId: data.localId };
}

// 2. Create Session
async function createSession(firebaseToken: string) {
  const response = await fetch('http://localhost:8000/api/sessions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
  });

  return await response.json();
}

// 3. Handle Gmail Auth
async function handleGmailAuth(sessionData: any, firebaseToken: string) {
  if (sessionData.requires_gmail_auth) {
    // Open OAuth URL in new window
    window.open(sessionData.gmail_auth_url, '_blank');

    // Wait for user to authorize
    await new Promise(resolve => {
      // Poll or wait for user confirmation
      setTimeout(resolve, 10000);
    });

    // Verify authorization
    const response = await fetch('http://localhost:8000/api/auth/gmail/status', {
      headers: { 'Authorization': `Bearer ${firebaseToken}` }
    });

    const status = await response.json();
    return status.is_authorized;
  }
  return true;
}

// 4. Connect WebSocket
function connectWebSocket(sessionId: string, userId: string) {
  const ws = new WebSocket(
    `ws://localhost:8000/api/voice/voice?session_id=${sessionId}&firebase_user_id=${userId}`
  );

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'start_voice_session' }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data.type);

    if (data.type === 'audio_response') {
      const audioData = atob(data.data);
      // Play audio...
    } else if (data.type === 'text_response') {
      console.log('Assistant:', data.text);
    }
  };

  return ws;
}

// Main flow
async function main() {
  // 1. Sign in
  const { token, userId } = await firebaseSignIn('user@example.com', 'password');

  // 2. Create session
  const session = await createSession(token);

  // 3. Handle Gmail auth
  if (!await handleGmailAuth(session, token)) {
    console.error('Gmail authorization failed');
    return;
  }

  // 4. Connect WebSocket
  const ws = connectWebSocket(session.session_id, userId);
}
```

---

## Rate Limits & Constraints

- **Max Concurrent Sessions:** 3 per user
- **Session TTL:** 24 hours
- **Firebase Token TTL:** 1 hour
- **Gmail Refresh Token TTL:** 30 days (in Redis)
- **User Config TTL:** 90 days (in Redis)
- **WebSocket Ping Interval:** 30 seconds
- **WebSocket Timeout:** 10 seconds
- **Gemini HTTP Timeout:** 5 minutes (300000ms)

---

## Best Practices

### Authentication & Authorization
1. **Always include Firebase token** in Authorization header for protected endpoints
2. **Check Gmail authorization** before attempting voice session
3. **Handle token expiration** gracefully and re-authenticate
4. **Verify authorization completion** after displaying OAuth URL
5. **Store tokens securely** (use httpOnly cookies or secure storage)

### Session Management
6. **Clean up sessions** when done (DELETE /api/sessions/{id})
7. **Handle WebSocket disconnections** and reconnect if needed
8. **Monitor session state** messages to track navigation
9. **Limit concurrent sessions** (max 3 per user)

### Audio Handling
10. **Use correct audio formats** (16kHz input, 24kHz output, PCM, mono)
11. **Implement stop_audio handling** to stop playback on interruption
12. **Clear audio queue** immediately when stop_audio received
13. **Handle Web Audio API properly** (request microphone permission)

### Error Handling
14. **Display errors to users** when Gmail re-auth is required
15. **Handle network failures** gracefully with retry logic
16. **Validate responses** before processing

### User Experience
17. **Show configuration options** to users (auto_mark_as_read, auto_send_drafts)
18. **Provide visual feedback** for connection status
19. **Display session state** (current message X of Y)
20. **Handle interruptions smoothly** with immediate audio stop

---

## OpenAPI Documentation

Interactive API documentation available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

---

For implementation details, see `AUTHENTICATION.md` and source code in `src/api/controllers/`.
