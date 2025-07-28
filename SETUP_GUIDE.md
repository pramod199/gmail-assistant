# Gmail Assistant Setup Guide

## Prerequisites
- Python 3.11+
- Redis server
- Google Cloud Project
- Firebase Project

## 🔧 **Step-by-Step Setup**

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Start Redis Server**
```bash
# Option A: Using Docker (Recommended)
docker-compose up redis -d

# Option B: Local Redis installation
redis-server
```

### 3. **Google Cloud Console Setup**

#### A. Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing one
3. Enable Gmail API:
   - Go to **APIs & Services** → **Library**
   - Search for "Gmail API" and enable it

#### B. Create OAuth 2.0 Credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **"+ CREATE CREDENTIALS"** → **OAuth 2.0 Client ID**
3. Choose **"Web application"**
4. Add redirect URIs:
   - `http://localhost:8000/api/auth/gmail/callback` (development)
   - `https://yourdomain.com/api/auth/gmail/callback` (production)
5. Download the JSON file as `credentials.json`
6. Place in project root: `/Users/pramod/src/projects/gmail-assistant/credentials.json`

### 4. **Firebase Setup**

#### A. Create Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create new project or use existing one
3. Enable Authentication (optional - for frontend)

#### B. Generate Service Account Key
1. Go to **Project Settings** → **Service Accounts**
2. Click **"Generate new private key"**
3. Download the JSON file
4. Place as: `/Users/pramod/src/projects/gmail-assistant/firebase-service-account.json`

### 5. **Environment Configuration**

#### Set Required Environment Variables (Optional)
```bash
# Gemini API Key (required for NLP features)
export GEMINI_API_KEY="your_gemini_api_key_here"

# Custom paths (optional)
export FIREBASE_SERVICE_ACCOUNT_PATH="/custom/path/to/firebase-key.json"
export GMAIL_CREDENTIALS_FILE="/custom/path/to/credentials.json"

# Redis configuration (if not using defaults)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_DB="0"
```

### 6. **Start the Server**
```bash
python app.py
```

Server will start at: `http://localhost:8000`

## 📋 **Testing with Postman**

### 1. **Import Collection**
1. Open Postman
2. Click **Import**
3. Import file: `Gmail_Assistant_API.postman_collection.json`

### 2. **Configure Variables**
1. In Postman, go to collection variables
2. Set `base_url` to `http://localhost:8000`
3. Set `firebase_token` to your Firebase ID token

### 3. **Get Firebase Token (for testing)**

**Method A: Using Firebase SDK (Frontend)**
```javascript
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';

const auth = getAuth();
const userCredential = await signInWithEmailAndPassword(auth, email, password);
const token = await userCredential.user.getIdToken();
```

**Method B: Using Firebase REST API**
```bash
curl -X POST \
  'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "returnSecureToken": true
  }'
```

### 4. **Test Flow**
1. **Test Public Endpoints** (no auth required):
   - `GET /` - API info
   - `GET /health` - Health check

2. **Test Authentication**:
   - `GET /api/auth/gmail/status` - Check Gmail auth status
   - `GET /api/auth/gmail/authorize` - Start OAuth (redirects to Google)

3. **Complete Gmail OAuth** (in browser):
   - Follow redirect URL from step 2
   - Authorize Gmail access
   - You'll be redirected back

4. **Test Gmail Operations**:
   - `GET /api/gmail/messages` - List messages
   - `POST /api/gmail/process` - Natural language requests
   - `POST /api/gmail/drafts` - Create drafts

## 🚀 **Production Deployment**

### Docker Deployment
```bash
# Update environment variables in docker-compose.yml
docker-compose up
```

### Manual Deployment
1. Set production environment variables
2. Update `FRONTEND_URL` in settings.py
3. Configure production OAuth redirect URIs
4. Set up SSL certificates
5. Use production Redis instance

## 🔍 **Troubleshooting**

### Common Issues

**1. Module Not Found Errors**
```bash
pip install -r requirements.txt
```

**2. Redis Connection Failed**
```bash
# Check if Redis is running
docker ps
# Or start Redis
docker-compose up redis -d
```

**3. Firebase Authentication Failed**
- Check `firebase-service-account.json` exists
- Verify file permissions
- Check Firebase project configuration

**4. Gmail OAuth Failed**
- Verify `credentials.json` exists
- Check OAuth redirect URIs in Google Cloud Console
- Ensure Gmail API is enabled

**5. Gemini API Errors**
- Set `GEMINI_API_KEY` environment variable
- Check API key validity
- Verify Gemini API quota

## 📝 **File Structure**
```
gmail-assistant/
├── firebase-service-account.json     # Firebase service account key
├── credentials.json                  # Google OAuth credentials
├── Gmail_Assistant_API.postman_collection.json  # Postman tests
├── app.py                           # FastAPI server
├── requirements.txt                 # Python dependencies
└── src/
    ├── config/settings.py           # Configuration management
    ├── api/                         # API controllers
    └── core/                        # Core Gmail/LLM logic
```