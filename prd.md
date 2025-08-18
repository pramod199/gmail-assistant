# Gmail Voice Assistant - Product Requirements Document

## 1. Product Overview

### 1.1 Product Vision
A voice-first Gmail assistant that enables users to manage their email hands-free through natural language interactions, powered by Gemini Live API with multi-user support and CarPlay integration.

### 1.2 Core Features
1. **Voice-Driven Email Reading** with intelligent navigation
2. **AI-Powered Email Summarization** using Gemini
3. **Voice-to-Text Email Drafting** with editing capabilities
4. **Smart Email Actions** (mark as read, star, archive, delete)
5. **Multi-User Authentication** via Firebase + Gmail OAuth
6. **Persistent Session Management** with Redis

### 1.3 Technical Stack
- **Backend**: Python FastAPI with single `/process-voice` endpoint
- **AI Layer**: Gemini Live API for voice processing and function calling
- **Authentication**: Firebase Auth + Gmail OAuth 2.0
- **Database**: Redis for session management and temporary data
- **Local Testing**: PyAudio Python client
- **Target Platform**: CarPlay integration

## 2. Functional Requirements

### 2.1 Authentication & Authorization

#### 2.1.1 User Management
**Requirements:**
- Users sign in using Gmail accounts through Firebase Auth
- Gmail OAuth 2.0 integration for API access
- Secure token storage and refresh mechanism
- Multi-user support with data isolation

**User Flow:**
1. User initiates sign-in → Firebase Auth with Gmail OAuth
2. System requests Gmail API permissions
3. User authorizes Gmail access
4. System creates user profile with Firebase UID
5. User gains access to voice assistant

#### 2.1.2 Session Management
**Purpose:** Maintain conversation context and navigation state during voice interactions

**Session Contains:**
- Current message being read
- Message queue and navigation position  
- Active draft state
- Conversation context for "next message" commands
- User's current filter (unread/important/starred)

**Session Timeout (Default: 24 hours):**
- **What expires**: Conversation context and navigation state
- **What persists**: Gmail authentication and access tokens
- **User impact**: After timeout, user starts fresh conversation but NO re-authentication needed
- **Example**: 
  - Before timeout: "Next message" continues from where you left off
  - After timeout: "Next message" won't work, need to start with "Read my messages"

**Important:** Session timeout does NOT affect Gmail authorization. Gmail tokens remain valid until explicitly revoked.

### 2.2 Voice-Driven Email Reading

#### 2.2.1 Message Retrieval
**Voice Commands:**
- "Read my messages" / "Check my email"
- "Read unread messages" 
- "Read important messages"
- "Read starred messages"

**System Behavior:**
- Fetch messages based on user request (default: unread)
- Cache message metadata in Redis for session
- Support message filtering (unread/important/starred/all)

#### 2.2.2 Message Navigation
**Voice Commands:**
- "Read the first message" → Preview first message in current filter
- "Read full message" → Complete message content
- "Next message" / "Previous message" → Sequential navigation
- "Read latest message from [sender]" → Find and read recent message from specific person
- "Read message about [topic]" → Search and read message with specific subject/content
- "Go back to previous message" → Return to previously read message

**Natural Language Search:**
- "Read latest message from John"
- "Find message from abc about project"
- "Show me the message about meeting"
- "Read the email from my boss"

**Message Formats:**
- **Preview**: Sender, timestamp, subject, first 1-2 sentences
- **Full**: Complete message content with intelligent formatting

**Navigation Context:**
Gmail messages are identified by unique IDs, not sequential numbers. The system maintains a session-based navigation context that allows "next/previous" commands to work naturally within the current message filter.

### 2.3 Email Summarization

#### 2.3.1 AI-Powered Summarization
**Voice Commands:**
- "Summarize this message"
- "Give me the key points"
- "What's the summary?"

**Gemini Integration:**
- Process message content for summarization
- Extract action items and key dates
- Handle different email types (newsletters, business, personal)

**Summary Format:**
- Main topic and key points
- Action items required
- Important dates mentioned
- Recommended next steps

### 2.4 Email Drafting & Composition

#### 2.4.1 Voice-to-Draft Creation
**Voice Commands:**
- "Draft a reply" / "Reply to this message"
- "Draft a new message"
- "Compose an email to [recipient]"

**Draft Creation Flow:**
1. System prompts for recipient (if new message)
2. System prompts for subject (if new message)
3. User dictates message content
4. Gemini processes and formats draft
5. **Draft stored temporarily in Redis** (not Gmail yet)
6. System reads draft back to user
7. User can approve, edit, or cancel

#### 2.4.2 Draft Editing & Management
**Voice Commands:**
- "Edit the draft"
- "Change the subject to [new subject]"
- "Make it more formal/casual"
- "Add [content] to the message"
- "Send the draft" → **Creates draft in Gmail then sends**
- "Save as draft" → **Creates draft in Gmail for later**
- "Cancel the draft" → **Deletes from Redis only**

**Draft Storage Strategy:**
- **Temporary Storage**: All draft editing happens in Redis for speed
- **Gmail Integration**: Draft created in Gmail only when:
  - User says "Send the draft" (create + send)
  - User says "Save as draft" (create as Gmail draft)
  - User explicitly requests to save to Gmail
- **Benefits**: Fast editing, no Gmail API calls during composition, user control over Gmail integration

### 2.5 Email Actions

#### 2.5.1 Message Actions
**Voice Commands:**
- "Mark as read" / "Mark as unread"
- "Star this message" / "Remove star"
- "Archive this message"
- "Delete this message"

**Smart Behavior:**
- Auto-ask to mark as read after reading message
- Confirmation for destructive actions (delete)
- Configurable auto-mark-as-read preference

#### 2.5.2 Batch Operations
**Voice Commands:**
- "Mark all as read"
- "Archive all read messages"

**Safety:**
- Confirmation required for batch operations
- Limit scope to prevent accidental data loss

### 2.6 User Preferences

#### 2.6.1 Configurable Settings
**Voice Commands:**
- "Turn on auto-mark as read"
- "Set message preview to short/long"

## 3. Technical Requirements

### 3.1 Backend Architecture (FastAPI)

#### 3.1.1 Authentication Endpoints
**Backend handles complete authentication flow:**
```
POST /auth/login
Body: { "firebase_token": "string" }
Response: { 
  "session_token": "jwt_token", 
  "gmail_auth_url": "oauth_url",
  "user_id": "firebase_uid"
}

POST /auth/gmail-callback
Body: { "authorization_code": "string", "user_id": "firebase_uid" }
Response: { "gmail_authorized": true, "user_profile": {} }

POST /auth/logout  
Headers: Authorization: Bearer <session_token>
Response: { "logged_out": true }

GET /auth/status
Headers: Authorization: Bearer <session_token>
Response: { "authenticated": true, "gmail_connected": true }
```

#### 3.1.2 Voice Processing Endpoint (Streaming)
```
WebSocket /ws/process-voice
Authorization: Bearer <session_token>

Connection Flow:
1. Client connects with session token
2. Real-time audio streaming begins
3. Server processes audio chunks with Gemini Live API
4. Server streams audio response back in real-time

Input Stream:
{
  "type": "audio_chunk",
  "data": "base64_audio_chunk",
  "chunk_index": 0,
  "is_final": false,
  "audio_format": {
    "sample_rate": 16000,
    "channels": 1,
    "format": "pcm16"
  }
}

Output Stream:
{
  "type": "audio_response",
  "data": "base64_audio_chunk", 
  "chunk_index": 0,
  "is_final": false,
  "text_response": "partial_or_complete_text",
  "session_state": {
    "current_message_id": "gmail_message_id_xyz",
    "total_messages": 15,
    "current_filter": "unread",
    "has_active_draft": false
  },
  "actions_performed": ["marked_as_read"]
}

End of Stream:
{
  "type": "stream_complete",
  "session_state": {...},
  "final_text_response": "complete_text_response"
}
```

#### 3.1.3 Streaming Audio Handling
**Real-time Voice Processing:**
- Accept audio chunks as they arrive (no waiting for complete recording)
- Process with Gemini Live API in real-time
- Stream audio response chunks back immediately
- Handle voice activity detection (VAD) for natural conversation flow

**Streaming Benefits:**
- Lower latency for voice interactions
- Natural conversation flow (interrupt/resume)
- Better user experience for long email reading
- Efficient bandwidth usage for CarPlay integration

**Connection Management:**
- Maintain WebSocket connection per user session
- Handle connection drops and reconnection
- Audio buffer management for quality assurance
- Session state synchronization across connection issues

#### 3.1.4 Function Calling Integration
**Gmail Functions for Gemini:**
```json
{
  "functions": [
    {
      "name": "read_messages",
      "description": "Fetch and read Gmail messages",
      "parameters": {
        "filter_type": "enum: unread|important|starred|all",
        "message_index": "integer: specific message index",
        "read_full": "boolean: full message vs preview"
      }
    },
    {
      "name": "navigate_messages",
      "description": "Navigate through message list or search for specific messages", 
      "parameters": {
        "direction": "enum: next|previous|first|last",
        "search_criteria": "object: {sender: string, subject_contains: string, date_range: string}",
        "message_id": "string: specific Gmail message ID"
      }
    },
    {
      "name": "summarize_message",
      "description": "Summarize specified message",
      "parameters": {
        "message_index": "integer: message to summarize"
      }
    },
    {
      "name": "mark_message",
      "description": "Change message status",
      "parameters": {
        "action": "enum: read|unread|star|unstar|archive|delete",
        "message_index": "integer: target message"
      }
    },
    {
      "name": "draft_email", 
      "description": "Create or manage email draft in temporary storage",
      "parameters": {
        "action": "enum: create|edit|save_to_gmail|send|cancel",
        "recipient": "string: email address",
        "subject": "string: email subject",
        "content": "string: email body",
        "draft_id": "string: existing draft ID for edits",
        "modifications": "object: specific changes for editing"
      }
    }
  ]
}
```

### 3.2 Gemini Live API Integration

#### 3.2.1 Streaming Voice Processing Flow
1. **Real-time Audio Input:**
   - Client establishes WebSocket connection
   - Audio chunks streamed continuously to server
   - Gemini Live API processes audio stream in real-time
   - Voice activity detection triggers processing

2. **Live Gmail Operations:**
   - Function calls extracted from audio stream
   - Gmail API operations executed as soon as intent is clear
   - Session state updated in Redis immediately

3. **Streaming Audio Response:**
   - Text response formatted for voice delivery
   - Gemini Live API generates audio response stream
   - Audio chunks streamed back to client in real-time
   - Client plays audio as chunks arrive

**Streaming Flow Example:**
```
User starts speaking: "Read my first message"
    ↓ (audio chunks streaming)
Gemini Live API: Processing audio stream → Function call detected
    ↓ (while user still speaking)
Gmail API: Fetch first unread message (parallel processing)
    ↓ (user finishes speaking)
Text Formatting: "You have 5 unread messages. First message from John..."
    ↓ (immediate audio generation)
Gemini Live API: Generate audio stream
    ↓ (audio chunks streaming back)
Client: Play audio response as chunks arrive
```

**Streaming Advantages:**
- **Ultra-low latency**: Processing starts before user finishes speaking
- **Natural conversation**: Real-time back-and-forth interaction
- **Interrupt handling**: User can interrupt long responses
- **Bandwidth efficient**: No large file uploads/downloads

#### 3.2.2 Audio Response Generation
**Method:** Use Gemini Live API's text-to-speech capabilities for consistent voice experience

**Text Formatting for Voice:**
- Remove HTML tags and formatting
- Convert timestamps to natural language ("2 hours ago" instead of "14:30")
- Break long emails into digestible chunks
- Add natural pauses and emphasis markers
- Handle email signatures and boilerplate text

**Audio Response Specification:**
```python
# Audio generation request to Gemini
audio_request = {
    "text": formatted_email_content,
    "voice_settings": {
        "speed": user_preferences.voice_speed,
        "tone": "conversational",
        "format": "mp3" or "wav"
    }
}
```

#### 3.2.3 Voice Response Scenarios

**Email Reading Responses:**
```
Preview: "First message from John at 2 PM, subject: Project Update. The project timeline has been updated for next week. Would you like me to read the full message?"

Full Message: "Here's the full message: [natural pauses] Hi team, [pause] I wanted to update you on the project timeline. [pause] We've moved the deadline to next Friday to accommodate the new requirements..."

Summary: "This message is about a project timeline change. Key points: deadline moved to next Friday, new requirements added, team meeting scheduled for Wednesday."
```

**Action Confirmations:**
```
"Message marked as read"
"Moved to next message" 
"Draft saved and ready to send"
"Email sent successfully"
```

**Error Handling:**
```
"I couldn't access your Gmail right now. Please try again."
"I didn't catch that command. You can say things like 'read my messages' or 'mark as read'."
"No unread messages found. Would you like to check important messages instead?"
```

#### 3.2.4 Gemini-Based Voice Response Generation

**Voice Response Strategy: Gemini Live API Only**
- Use Gemini Live API for both voice input processing AND audio output generation
- Maintain conversation consistency with single AI service
- Leverage Gemini's natural language understanding for voice-optimized responses

**Implementation Approach:**
```python
# After executing Gmail function calls:
1. Format email data for voice-friendly presentation
2. Send formatted text back to Gemini Live API for audio generation
3. Receive generated audio response
4. Return audio to client for playback
```

**Voice Optimization with Gemini:**
- Request Gemini to format responses specifically for voice delivery
- Use natural language prompts to control response tone and pacing
- Leverage Gemini's context awareness for personalized voice responses
- Handle different content types (short confirmations vs long email reading) appropriately

**Benefits of Gemini-Only Approach:**
- Single service dependency and API integration
- Consistent voice personality and conversation flow
- Natural language control over voice generation
- Built-in context awareness for better responses

#### 3.2.5 Error Handling
- API rate limit management with exponential backoff
- Fallback for Gemini API failures
- Gmail API quota monitoring
- Session recovery mechanisms

### 3.3 Gmail API Integration

#### 3.3.1 Required Scopes
- `https://www.googleapis.com/auth/gmail.readonly` - Read messages
- `https://www.googleapis.com/auth/gmail.modify` - Mark as read/unread, star
- `https://www.googleapis.com/auth/gmail.compose` - Draft and send emails

#### 3.3.2 Data Caching Strategy
- Cache message metadata in Redis (TTL: 1 hour)
- Invalidate cache on user actions
- Batch API calls where possible

### 3.4 Database Design (Redis)

#### 3.4.1 Table Structure by Use Case

**User Authentication Table:**
```redis
# Stores all user authentication related data
user_auth = {
  "{firebase_uid}": {
    email: string,
    firebase_token: encrypted_string,
    gmail_access_token: encrypted_string,
    gmail_refresh_token: encrypted_string,
    session_token: jwt_string,
    created_at: timestamp,
    last_login: timestamp,
    gmail_authorized: boolean
  }
}
```

**Session Management Table:**
```redis
# Stores all active session data
user_sessions = {
  "{firebase_uid}": {
    current_message_id: string (Gmail message ID),
    message_queue: array (Gmail message IDs in current filter),
    current_filter: enum('unread', 'important', 'starred', 'all'),
    active_draft_id: string,
    last_active: timestamp,
    conversation_context: array,
    navigation_history: array (previously read message IDs),
    current_search_criteria: object (for search-based navigation)
  }
}
```

**User Preferences Table:**
```redis
# Stores user configuration and preferences
user_preferences = {
  "{firebase_uid}": {
    auto_mark_read: boolean,
    preview_length: enum('short', 'medium', 'long'),
    default_filter: enum('unread', 'important', 'starred', 'all'),
    session_timeout: number (hours),
    voice_speed: enum('slow', 'normal', 'fast'),
    notification_settings: object
  }
}
```

**Message Cache Table:**
```redis
# Temporary message storage for performance (TTL: 1 hour)
message_cache = {
  "{firebase_uid}_{filter_type}": {
    messages: array,
    total_count: number,
    cached_at: timestamp,
    last_sync: timestamp
  }
}
```

**Draft Storage Table:**
```redis
# Temporary draft storage before Gmail creation
draft_storage = {
  "{firebase_uid}_{draft_id}": {
    recipient: string,
    subject: string,
    content: string,
    reply_to_message_id: string,
    draft_type: enum('new', 'reply', 'forward'),
    created_at: timestamp,
    modified_at: timestamp,
    status: enum('editing', 'ready_to_send', 'saved_to_gmail', 'sent'),
    gmail_draft_id: string (null until saved to Gmail)
  }
}
```

### 3.5 Local Testing with PyAudio (Streaming)

#### 3.5.1 PyAudio Streaming Client Requirements
**Real-time Audio Streaming:**
- Establish WebSocket connection to `/ws/process-voice`
- Stream audio chunks from microphone in real-time (configurable chunk size)
- Receive and play audio response chunks as they arrive
- Handle voice activity detection for natural conversation flow

**Streaming Client Features:**
```python
# PyAudio streaming client capabilities
class StreamingVoiceClient:
    - real_time_audio_capture()      # Continuous microphone streaming
    - websocket_audio_sender()       # Send audio chunks via WebSocket
    - audio_response_receiver()      # Receive and buffer audio chunks
    - real_time_audio_playback()     # Play response as chunks arrive
    - voice_activity_detection()     # Detect speech start/end
    - session_state_management()     # Handle session updates from server
    - connection_recovery()          # Reconnect on connection drops
```

**Audio Streaming Configuration:**
- Sample rate: 16kHz (optimal for Gemini Live API)
- Chunk size: 1024 samples (64ms chunks for low latency)
- Audio format: PCM 16-bit (compatible with most voice processing)
- Buffer management: Circular buffer for smooth playback
- VAD sensitivity: Configurable for different environments

**Testing Experience:**
- **Natural conversation**: Start speaking, get immediate responses
- **Interrupt capability**: Stop long email reading by speaking
- **Real-time feedback**: Visual indicators for audio streaming status
- **Debug mode**: Display streaming stats, connection status, session state
- **Low latency**: Target <500ms total processing time

#### 3.5.2 Streaming Testing Scenarios
- **Real-time Authentication**: 
  - WebSocket connection with session token validation
  - Streaming audio for voice commands during auth flow
- **Live Message Reading**: 
  - Stream audio while fetching emails in parallel
  - Interrupt long email reading with "next message" command
- **Continuous Conversation**:
  - "Read my messages" → immediate streaming response
  - "Next message" → seamless transition without re-connection
- **Draft Creation Flow**:
  - Stream draft content continuously
  - Real-time editing with voice commands
- **Connection Recovery**: 
  - Test reconnection during active conversations
  - Resume session state after brief disconnections
- **Multi-turn Conversations**:
  - Extended back-and-forth interactions
  - Context preservation across streaming sessions

## 4. Non-Functional Requirements

### 4.1 Performance
- Voice command processing: < 2 seconds response time
- Message loading: < 3 seconds for email content
- Concurrent users: Support 100+ users initially
- Audio streaming: Low latency for voice responses

### 4.2 Security
- All Gmail tokens encrypted at rest
- User data isolation enforced
- API rate limiting and request validation  
- Session timeout and secure logout
- GDPR-compliant data handling

### 4.3 Reliability
- 99.5% service availability target
- Graceful degradation for API failures
- Redis data persistence and backup
- Comprehensive error logging and monitoring

## 5. Integration Specifications

### 5.1 Firebase Integration
- Firebase Auth for user authentication
- Custom claims for user permissions
- Secure token validation on backend
- User profile management

### 5.2 CarPlay Integration (Future)
**Streaming-First Design Benefits for CarPlay:**
- **Ultra-low latency**: Critical for safe driving interaction
- **Real-time conversation**: Natural voice interaction while driving
- **Interrupt capability**: Stop long email reading instantly for safety
- **Bandwidth optimization**: Efficient cellular data usage in vehicles
- **Connection resilience**: Handle cellular network fluctuations gracefully

**CarPlay-Specific Streaming Requirements:**
- Audio streaming over cellular networks (3G/4G/5G compatibility)
- Background audio processing while other CarPlay apps are active
- Voice activity detection optimized for vehicle noise
- Automatic audio ducking for navigation/calls
- Session handoff from PyAudio testing client to CarPlay

## 6. Success Metrics

### 6.1 Technical Metrics
- Voice command accuracy: >90%
- Average response time: <2 seconds  
- API error rate: <5%
- Session completion rate: >85%

### 6.2 User Experience Metrics
- Email reading task completion: >95%
- Draft creation success rate: >90%
- User preference adoption: >70%
- Voice interaction satisfaction

---

*This PRD defines the core requirements for implementing a voice-driven Gmail assistant with multi-user support, designed for CarPlay integration using FastAPI, Gemini Live API, and PyAudio for local testing.*