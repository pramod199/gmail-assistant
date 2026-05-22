# Gmail Voice Assistant

A voice-first Gmail assistant built on Google's Gemini Live API. Talk naturally to read, navigate, summarize, and reply to email — hands-free. Designed for use cases like driving and CarPlay.

The project is split into two services:

- **`app/`** — FastAPI backend that streams audio to/from Gemini Live, handles Gmail API calls, and stores per-user sessions in Redis.
- **`web-client/`** — Next.js web client for browser-based voice interaction and sign-in.

## Features

- Real-time streaming voice conversation (WebSocket + Gemini Live)
- Natural-language Gmail commands: read, navigate, summarize, mark, archive, draft, send
- Multi-user support with isolated sessions
- Firebase Authentication for app access + Google OAuth for Gmail access
- Redis-backed sessions and credential storage with automatic token refresh

## Architecture

```
Browser / Voice Client ──WebSocket──▶ FastAPI ──▶ Gemini Live API
                                         │
                                         ├──▶ Gmail API
                                         └──▶ Redis (sessions, credentials)
```

## Prerequisites

- Python 3.11+
- Node.js 20+ (for the web client)
- Redis 7+ (local or via Docker)
- A Google Cloud project with Gmail API enabled
- A Firebase project
- A Gemini API key

## Credentials Setup

You need three sets of credentials. Each one goes in a specific place.

### 1. Gemini API Key

1. Go to https://aistudio.google.com/apikey
2. Click **Create API key** and copy it.
3. Add to `.env` as `GEMINI_API_KEY=...`.

### 2. Google Cloud OAuth (Gmail access)

1. Open https://console.cloud.google.com and create (or pick) a project.
2. Enable the Gmail API: **APIs & Services → Library → "Gmail API" → Enable**.
3. Configure the OAuth consent screen:
   - **APIs & Services → OAuth consent screen**
   - User type: **External** (or Internal if you're on Workspace)
   - Add the scope `https://www.googleapis.com/auth/gmail.modify`
   - Add your email as a **Test user** while the app is in testing mode
4. Create the OAuth client:
   - **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/api/auth/gmail/callback`
5. Download the JSON and save it as `credentials.json` in the project root.

### 3. Firebase (user authentication)

1. Open https://console.firebase.google.com and create a project.
2. **Build → Authentication → Get started** and enable the **Email/Password** sign-in provider.
3. Get the **Web API key**:
   - **Project settings (gear icon) → General → Your apps → Web app**
   - Register a web app if you haven't, copy `apiKey`.
   - Add to `.env` as `FIREBASE_WEB_API_KEY=...` and to `web-client/.env.local` as `NEXT_PUBLIC_FIREBASE_API_KEY=...`.
4. Get the **service account key** (server-side admin SDK):
   - **Project settings → Service accounts → Generate new private key**
   - Save the downloaded JSON as `firebase-service-account.json` in the project root.

> ⚠️ `credentials.json`, `firebase-service-account.json`, and `.env` are all in `.gitignore`. Never commit them.

### 4. Configure environment variables

```bash
cp .env.example .env
# edit .env and fill in your real values
```

For the web client:

```bash
cd web-client
cat > .env.local <<EOF
NEXT_PUBLIC_FIREBASE_API_KEY=your_firebase_web_api_key
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000/api/voice
EOF
```

## Running the Backend

### Option A — Docker (recommended)

Starts the FastAPI server and Redis together:

```bash
docker-compose up --build
```

API will be available on `http://localhost:7552` (mapped from container port 8000).

### Option B — Local

```bash
# 1. Start Redis (in another terminal or via Docker)
docker run -p 6379:6379 redis:7-alpine

# 2. Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run the server
python -m app.main
# or, with reload:
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `curl http://localhost:8000/`
Interactive API docs: http://localhost:8000/docs

## Running the Web Client

In a separate terminal:

```bash
cd web-client
npm install
npm run dev
```

Open http://localhost:3000.

1. Sign in with the Firebase email/password account you created.
2. The app will prompt you to authorize Gmail on first use — complete the Google OAuth flow.
3. Hit the mic and start talking.

## Voice Commands

Some examples of what you can say:

- "Read my unread emails"
- "Next message" / "Previous message"
- "Summarize this email"
- "Mark this as read" / "Star this"
- "Reply saying I'll be there by 5"
- "Find emails from Alice about the launch"

## Project Layout

```
gmail-assistant/
├── app/                  # FastAPI backend
│   ├── main.py           # ASGI entrypoint
│   ├── config.py         # Pydantic settings
│   ├── auth.py           # Firebase + Gmail OAuth glue
│   ├── api/              # Router aggregation
│   ├── routers/          # auth, gmail, voice, websocket, health
│   ├── services/         # gemini, gmail, redis, session, drafts
│   ├── models/           # Internal domain models
│   ├── schemas/          # Pydantic API contracts
│   └── utils/            # Logging, parsing helpers
├── web-client/           # Next.js web client
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Troubleshooting

- **`OAuth credentials file not found`** — `credentials.json` is missing from the project root.
- **`NEXT_PUBLIC_FIREBASE_API_KEY is not set`** — fill it in `web-client/.env.local`.
- **Gmail authorization keeps looping** — your OAuth client must be a **Web application** type with `http://localhost:8000/api/auth/gmail/callback` listed under Authorized redirect URIs.
- **`access_denied` on the consent screen** — add your Google account as a Test user under OAuth consent screen settings.
- **Redis connection refused** — make sure Redis is running on `localhost:6379`, or set `REDIS_HOST` / `REDIS_PORT` in `.env`.

## Contributing

Pull requests welcome. For larger changes, please open an issue first to discuss what you'd like to change.
