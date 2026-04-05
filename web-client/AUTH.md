# Web Client Authentication

End-to-end description of how the Next.js web client authenticates against the Gmail Assistant backend.

## Two authentication layers

The app stacks two independent auth systems:

1. **Firebase Authentication** — identifies the user to *our* backend.
2. **Gmail OAuth 2.0** — authorizes *our backend* to call the Gmail API on the user's behalf.

A user must complete layer 1 to create a session, and layer 2 before the voice assistant can actually read/modify mail.

---

## Layer 1 — Firebase sign-in (client → Firebase)

The client talks directly to Google's Identity Toolkit REST API using the project's public Web API key. The backend is not involved in this exchange.

**File:** `src/lib/firebase-auth.ts`

- Endpoint: `POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<FIREBASE_WEB_API_KEY>`
- Body: `{ email, password, returnSecureToken: true }`
- Returns: `{ idToken, localId, email }`
  - `idToken` — Firebase ID token (JWT), short-lived (~1h). Sent to the backend as a Bearer token.
  - `localId` — Firebase UID, used as the stable user identifier throughout the system.

**Env var:** `NEXT_PUBLIC_FIREBASE_API_KEY` (there is a hardcoded fallback in `firebase-auth.ts`).

The client stores `idToken` and `localId` in refs inside `useVoiceSession` (`src/lib/use-voice-session.ts`). They are not persisted — a page reload re-runs sign-in.

---

## Layer 2 — Backend-verified API calls

Every protected REST call carries the Firebase ID token in the `Authorization` header:

```
Authorization: Bearer <idToken>
```

The backend (`app/auth.py`, `get_current_user` dependency) verifies the token with the Firebase Admin SDK, extracts `uid`/`email`, and auto-creates the user in Redis on first request. The resolved `User` is injected into every protected route.

The backend also accepts an `X-API-Key` header as an alternative (server-side testing only — not used by the web client).

**Used by the client for:**
- `POST /api/sessions` — create voice session (`createSession` in `src/lib/session-api.ts`)
- `DELETE /api/sessions/:id` — tear down
- `GET/PUT /api/config/user/voice-persona`
- Gmail OAuth status/authorize/revoke endpoints

---

## Layer 3 — Gmail OAuth authorization

Firebase sign-in alone does **not** grant access to the user's inbox. The first time a user creates a session, the backend checks whether it holds Gmail OAuth credentials for their UID in Redis. If not, the session response comes back as:

```json
{
  "session_id": "…",
  "gmail_authorized": false,
  "requires_gmail_auth": true,
  "gmail_auth_url": "https://accounts.google.com/o/oauth2/auth?..."
}
```

The client (`use-voice-session.ts`, `connect()`) surfaces `gmail_auth_url` via the `gmailAuthUrl` state. The UI is expected to open that URL so the user can complete Google's consent flow.

**OAuth flow (backend-owned, `app/routers/auth.py`):**

1. Client navigates user to `gmail_auth_url`. The `state` parameter encodes `<user_id>:<nonce>:<hmac>` signed with `OAUTH_STATE_SECRET` for CSRF protection.
2. User consents on Google's screen.
3. Google redirects to `GET /api/auth/gmail/callback?code=...&state=...`. This endpoint is **public** (no Firebase token) — trust is established by verifying the state HMAC.
4. Backend exchanges the code for access + refresh tokens and stores them in Redis keyed by the Firebase UID extracted from `state`.
5. Response is currently JSON (`GmailCallbackResponse`). TODOs in `gmail_callback` note that this will eventually redirect back to `FRONTEND_URL/auth/success` or `/auth/error`.

After the user completes this once, subsequent `POST /api/sessions` calls return `gmail_authorized: true` and a session id the client can open a WebSocket against.

**Scopes requested:** `https://www.googleapis.com/auth/gmail.modify` (see `GMAIL_SCOPES` in `app/config.py`).

**Redirect URIs:**
- Dev: `http://localhost:8000/api/auth/gmail/callback`
- Prod: configured via `OAUTH_REDIRECT_URI_PROD`

The refresh token stays in backend Redis; the client never sees Google access tokens.

---

## Layer 4 — WebSocket voice channel

The WebSocket at `/api/voice/voice` currently authenticates via query parameters, **not** a Bearer token:

```
ws://.../api/voice/voice?session_id=<id>&firebase_user_id=<localId>
```

(See `src/lib/websocket-manager.ts` and `app/routers/websocket.py`.) The server trusts the `session_id` + `firebase_user_id` pair because the session was already created through an authenticated REST call. There is a separate `authenticate_websocket_user(token=...)` helper in `app/auth.py` that validates a Firebase ID token passed as `?token=` — it exists in the backend but is not what the voice WebSocket is wired to today. If you need stronger WS auth, switch to that path.

---

## End-to-end flow (happy path)

```
[Web client]                       [Backend]                      [Google]
     |                                  |                              |
     |-- POST identitytoolkit --------- (direct to Google) ----------->|
     |<- idToken, localId -----------------------------------|         |
     |                                  |                              |
     |-- POST /api/sessions ----------->|                              |
     |   Authorization: Bearer idToken  |-- verify_id_token_async ---->|
     |                                  |<- uid, email ----------------|
     |                                  |                              |
     |<- 200 {requires_gmail_auth:true, gmail_auth_url} (first time)   |
     |                                  |                              |
     |   (user opens gmail_auth_url in browser)                        |
     |------------------------------------------------- consent ------>|
     |                                  |<- GET /callback?code&state --|
     |                                  |-- exchange code ------------>|
     |                                  |<- access+refresh tokens -----|
     |                                  |   (stored in Redis by uid)   |
     |                                  |                              |
     |-- POST /api/sessions ----------->|                              |
     |<- 200 {session_id, gmail_authorized:true}                       |
     |                                  |                              |
     |-- WS /api/voice/voice?session_id=…&firebase_user_id=…           |
     |<==> audio + JSON control frames  |<==> Gemini Live + Gmail APIs |
```

---

## Environment variables (web client)

- `NEXT_PUBLIC_FIREBASE_API_KEY` — Firebase Web API key (public, safe in client).
- `NEXT_PUBLIC_API_BASE_URL` — default `http://localhost:8000/api`.
- `NEXT_PUBLIC_WS_BASE_URL` — default `ws://localhost:8000/api/voice`.

## Key files

| File | Role |
|---|---|
| `src/lib/firebase-auth.ts` | Firebase password sign-in, returns ID token |
| `src/lib/session-api.ts` | Authenticated REST calls (Bearer idToken) |
| `src/lib/websocket-manager.ts` | Voice WS connection using session_id + firebase_user_id |
| `src/lib/use-voice-session.ts` | Orchestrates login → createSession → WS → audio |
| `src/components/LoginForm.tsx` | Email/password form |

## Known quirks / things to pass on

- `useVoiceSession` auto-logs in with `test@example.com / testpass123` on mount (dev convenience — remove before shipping).
- Firebase ID tokens expire in ~1 hour. There is no refresh logic on the client today; a long-lived session will eventually fail on the next REST call. If this becomes a problem, add Firebase's `refreshToken` handling or swap to the Firebase JS SDK.
- The OAuth callback currently returns JSON instead of redirecting to the frontend. The TODOs in `app/routers/auth.py` mark where to re-enable `RedirectResponse(FRONTEND_URL/auth/success)` once the client route exists.
- The voice WebSocket authenticates by `session_id` + `firebase_user_id` query params, not a Firebase token. Treat session ids as capability tokens.
