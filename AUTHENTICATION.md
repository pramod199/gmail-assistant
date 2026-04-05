# Authentication Architecture

This document explains the dual authentication system in the Gmail Voice Assistant.

## Overview

The system uses **two separate authentication mechanisms**:

1. **Firebase Authentication** - For app-level access control
2. **Gmail OAuth 2.0** - For Gmail API access

## Why Two Separate Auth Systems?

### Firebase Authentication (App Auth)
- **Purpose:** Identify and authenticate users of YOUR application
- **Controls:** Who can use the Gmail Voice Assistant
- **Managed By:** Your Firebase project
- **Token Type:** Firebase ID Token (JWT)
- **Duration:** 1 hour

### Gmail OAuth (Gmail Auth)
- **Purpose:** Grant access to user's Gmail data
- **Controls:** What Gmail operations can be performed
- **Managed By:** Google OAuth 2.0
- **Token Type:** OAuth Access Token + Refresh Token
- **Duration:** Access token 1 hour, Refresh token indefinite

## Authentication Flow

### 1. User Signs In (Firebase Auth)

```
Client                          Server                    Firebase
  │                               │                          │
  │ POST email/password          │                          │
  ├──────────────────────────────>│                          │
  │                               │ Verify with Firebase     │
  │                               ├─────────────────────────>│
  │                               │<─────────────────────────┤
  │<──────────────────────────────┤                          │
  │ Firebase ID Token             │                          │
```

### 2. Session Creation with Gmail Auth Check

```
Client                          Server                    Redis
  │                               │                          │
  │ POST /api/sessions            │                          │
  │ (Firebase token)              │                          │
  ├──────────────────────────────>│                          │
  │                               │ Validate Firebase token  │
  │                               │ Extract user_id          │
  │                               │                          │
  │                               │ Check Gmail credentials  │
  │                               ├─────────────────────────>│
  │                               │<─────────────────────────┤
  │                               │                          │
  │                               │ IF NO CREDENTIALS:       │
  │                               │   Generate OAuth URL     │
  │                               │                          │
  │<──────────────────────────────┤                          │
  │ session_id                    │                          │
  │ gmail_auth_url (if needed)    │                          │
```

### 3. Gmail Authorization (First Time / Re-auth)

```
Client                    Server                Google OAuth
  │                         │                         │
  │ Open gmail_auth_url     │                         │
  ├─────────────────────────┼────────────────────────>│
  │                         │                         │
  │                         │                    [User grants]
  │                         │                         │
  │                         │<────────────────────────┤
  │                         │ OAuth callback          │
  │                         │ (authorization code)    │
  │                         │                         │
  │                         │ Exchange code for tokens│
  │                         ├────────────────────────>│
  │                         │<────────────────────────┤
  │                         │ Access + Refresh tokens │
  │                         │                         │
  │                         │ Store in Redis          │
  │                         ├───────────>Redis        │
```

### 4. Automatic Token Refresh

```
Client                    Server                Redis
  │                         │                     │
  │ Gmail API request       │                     │
  ├────────────────────────>│                     │
  │                         │ Get credentials     │
  │                         ├────────────────────>│
  │                         │<────────────────────┤
  │                         │                     │
  │                         │ IF EXPIRED:         │
  │                         │   Refresh token     │
  │                         │   Update Redis      │
  │                         │                     │
  │                         │ IF REFRESH FAILS:   │
  │                         │   Delete credentials│
  │                         │   Return error      │
  │                         │                     │
  │<────────────────────────┤                     │
  │ Success / Need re-auth  │                     │
```

## Server Implementation Details

### Session Creation (`POST /api/sessions`)

```python
async def create_session(request_data, current_user):
    user_id = current_user["user_id"]  # From Firebase token

    # Check Gmail authorization
    gmail_authorized = await credential_store.has_credentials(user_id)

    if not gmail_authorized:
        # Generate OAuth URL for this user
        gmail_auth_url = _generate_auth_url(user_id)

        return SessionResponse(
            session_id=session.id,
            gmail_authorized=False,
            gmail_auth_url=gmail_auth_url,
            requires_gmail_auth=True
        )

    # Session created, Gmail ready
    return SessionResponse(
        session_id=session.id,
        gmail_authorized=True,
        requires_gmail_auth=False
    )
```

### Token Refresh (`get_credentials`)

```python
async def get_credentials(user_id: str) -> Optional[Credentials]:
    # Get from Redis
    credentials = await redis_client.get(f"gmail_creds:{user_id}")

    # Check if expired
    if credentials.expired and credentials.refresh_token:
        try:
            # Refresh token
            credentials.refresh(Request())
            # Update Redis
            await store_credentials(user_id, credentials)
        except Exception:
            # Refresh failed - remove credentials
            await remove_credentials(user_id)
            return None

    return credentials
```

## Client Implementation

### Session Creation Flow

```python
# 1. Create session
response = await session.post("/api/sessions", headers=auth_headers)
data = response.json()

# 2. Check Gmail auth
if data["requires_gmail_auth"]:
    print(f"Open this URL: {data['gmail_auth_url']}")
    input("Press Enter after authorizing...")

    # 3. Verify authorization completed
    status = await session.get("/api/auth/gmail/status")
    if status["is_authorized"]:
        print("Gmail authorized!")
    else:
        print("Authorization incomplete")
```

## Security Considerations

### Firebase Token Security
- **Transmission:** HTTPS only
- **Storage:** Client memory only (never persisted)
- **Validation:** Every request validated against Firebase Admin SDK
- **Expiration:** Auto-expires after 1 hour

### Gmail OAuth Security
- **State Parameter:** CSRF protection with SHA256 hash
- **Refresh Token:** Stored in Redis with 30-day TTL
- **Access Token:** Never stored, regenerated from refresh token
- **Scope Limitation:** Only requested scopes granted

## Error Handling

### Firebase Auth Errors
- `401 Unauthorized` - Invalid/expired Firebase token → Re-authenticate
- `403 Forbidden` - Valid token but insufficient permissions

### Gmail Auth Errors
- `gmail_not_authorized` - No credentials stored → Show OAuth URL
- `refresh_failed` - Refresh token invalid → Re-authorize
- `scope_insufficient` - Missing required scopes → Re-authorize with new scopes

## Environment Configuration

### Server (.env)
```bash
# Firebase Admin SDK
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json

# Gmail OAuth
GMAIL_CREDENTIALS_FILE=./credentials.json
OAUTH_REDIRECT_URI_PROD=https://yourdomain.com/api/auth/gmail/callback
OAUTH_STATE_SECRET=your_secret_key

# Redis (for credential storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB_CREDENTIALS=0
```

### Client
```bash
# Firebase Web API (for client-side auth)
FIREBASE_WEB_API_KEY=your_firebase_web_api_key
```

## Best Practices

### For Server Development
1. Always validate Firebase token before any operation
2. Check Gmail credentials before Gmail operations
3. Handle refresh token expiration gracefully
4. Log auth failures for debugging
5. Use secure state parameters in OAuth flow

### For Client Development
1. Handle Gmail auth flow in session creation
2. Display clear OAuth URLs to users
3. Verify authorization before proceeding
4. Handle re-authorization gracefully
5. Never store Firebase tokens in localStorage

## Common Scenarios

### Scenario 1: New User
1. User signs in with Firebase (email/password)
2. Client creates session → Server returns `gmail_auth_url`
3. User opens URL and authorizes Gmail
4. Server stores refresh token
5. Session proceeds normally

### Scenario 2: Returning User with Valid Tokens
1. User signs in with Firebase
2. Client creates session → Server confirms Gmail authorized
3. Session proceeds immediately

### Scenario 3: Returning User with Expired Refresh Token
1. User signs in with Firebase
2. Client creates session → Server checks credentials
3. Server attempts token refresh → Fails
4. Server deletes invalid credentials
5. Server returns `gmail_auth_url`
6. User re-authorizes Gmail

### Scenario 4: User Revoked Gmail Access
1. User previously revoked access via Google Account settings
2. Client creates session → Server has old credentials
3. First Gmail operation fails
4. Server detects revocation, deletes credentials
5. Next session creation returns `gmail_auth_url`

## Monitoring & Debugging

### Logs to Monitor
- Firebase token validation failures
- Gmail token refresh attempts
- Gmail token refresh failures
- OAuth callback success/failures
- Credential deletion events

### Debug Endpoints
- `GET /api/auth/gmail/status` - Check current auth status
- `DELETE /api/auth/gmail/revoke` - Manually revoke access (testing)

## Future Improvements

1. **Firebase Token Refresh** - Implement client-side token refresh
2. **Credential Encryption** - Encrypt refresh tokens in Redis
3. **Audit Logging** - Track all auth events
4. **Rate Limiting** - Prevent auth abuse
5. **Multi-Account** - Support multiple Gmail accounts per user
