# Gmail Assistant API Documentation

## Overview
FastAPI-based REST API for Gmail management with Firebase authentication and natural language processing.

## Authentication
All endpoints (except public ones) require Firebase ID token in Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

## Base URL
- Development: `http://localhost:8000`
- Production: `https://yourdomain.com`

## Endpoints

### Public Endpoints

#### Health Check
- `GET /` - API info
- `GET /health` - Health status

### Authentication Endpoints

#### Gmail OAuth Management
- `GET /api/auth/gmail/status` - Check Gmail authorization status
- `GET /api/auth/gmail/authorize` - Start Gmail OAuth flow
- `GET /api/auth/gmail/callback` - OAuth callback (used by Google)
- `DELETE /api/auth/gmail/revoke` - Revoke Gmail access

### Gmail Operations

#### Natural Language Processing
- `POST /api/gmail/process` - Process natural language requests
  ```json
  {
    "query": "Show me my unread emails"
  }
  ```

#### Message Management
- `GET /api/gmail/messages` - List messages with optional filters
  - Query params: `max_results`, `query` (Gmail search syntax)
- `GET /api/gmail/messages/{id}` - Get specific message
- `POST /api/gmail/messages/{id}/mark-read` - Mark message as read

#### Draft Management
- `POST /api/gmail/drafts` - Create new draft
  ```json
  {
    "to": "recipient@example.com",
    "subject": "Subject line",
    "body": "Email content"
  }
  ```
- `GET /api/gmail/drafts` - List user's drafts
- `GET /api/gmail/drafts/{id}` - Get draft details
- `POST /api/gmail/drafts/{id}/send` - Send draft
- `DELETE /api/gmail/drafts/{id}` - Delete draft

## Configuration

### Environment Variables
All configuration is managed in `src/config/settings.py`. Key variables:

- `GEMINI_API_KEY` - Google Gemini API key
- `FIREBASE_SERVICE_ACCOUNT_PATH` - Firebase service account JSON path
- `REDIS_HOST/PORT/DB` - Redis connection settings
- `API_HOST/PORT` - Server binding settings
- `FRONTEND_URL` - Frontend application URL for OAuth redirects

### OAuth Setup
1. Create Google Cloud Project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download `credentials.json`
5. Configure redirect URIs in Google Cloud Console

### Firebase Setup
1. Create Firebase project
2. Generate service account key
3. Place as `firebase-service-account.json`
4. Configure Firebase Authentication

## Running the Server

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis
docker-compose up redis -d

# Run server
python app.py
```

### Production (Docker)
```bash
# Build and run all services
docker-compose up
```

## API Flow

1. **User Authentication**: Frontend authenticates user with Firebase
2. **Gmail Authorization**: User authorizes Gmail access via OAuth
3. **API Requests**: Frontend makes authenticated API calls
4. **Natural Language**: Process requests with Gemini LLM
5. **Gmail Operations**: Execute Gmail actions with stored credentials

## Error Handling

- `401` - Authentication required (missing/invalid Firebase token)
- `400` - Bad request (invalid parameters)
- `404` - Resource not found
- `500` - Server error

## Security Features

- Firebase token validation
- CSRF-protected OAuth state parameters
- User-isolated credential storage
- Automatic token refresh
- Rate limiting (Docker setup)