# Gmail Assistant - Async Migration Guide

## Overview
This guide details the remaining work required to complete the async Redis migration and implement best practices from auto-translator-server.

## ✅ Completed Migrations

### 1. Core Infrastructure
- ✅ `src/core/session/redis_client.py` - Fully async with connection lifecycle
- ✅ `src/core/auth/firebase_async.py` - Created async Firebase wrapper
- ✅ `src/core/background_tasks.py` - Background task manager created
- ✅ `src/core/session/voice_session_manager.py` - Hybrid Redis session manager
- ✅ `app.py` - Lifecycle hooks implemented

### 2. Session & Auth Services
- ✅ `src/core/session/session_manager.py` - All methods converted to async
- ✅ `src/core/auth/user_credential_store.py` - All methods converted to async
- ✅ `src/api/controllers/auth_controller.py` - Updated to use async methods
- ✅ `src/core/config/user_config_manager.py` - Already uses async Redis

### 3. WebSocket Utilities
- ✅ `src/api/websocket/websocket_helpers.py` - Safe WebSocket helpers created

### 4. REST API
- ✅ `src/api/controllers/session_controller.py` - Session management endpoints

## ⚠️ Critical Remaining Work

### Priority 1: Update Voice WebSocket Handler

**File**: `src/api/websocket/voice_handler.py`

**Current Issues:**
1. Not integrated with new `voice_session_manager`
2. Stores connections in simple dict instead of session manager
3. No safe WebSocket close utilities
4. Task lifecycle management needs improvement

**Required Changes:**

```python
# 1. Update imports
from ...core/session.voice_session_manager import voice_session_manager
from ..websocket.websocket_helpers import safe_websocket_close, is_websocket_connected

# 2. Update connect() method
async def connect(self, websocket: WebSocket, firebase_user_id: str):
    # Get or create voice session
    session = await voice_session_manager.get_session(session_id)
    if not session or not session.active:
        await safe_websocket_close(websocket, code=1008, reason="Invalid session")
        return None

    # Validate session ownership
    if session.user_id != firebase_user_id:
        await safe_websocket_close(websocket, code=1008, reason="Unauthorized")
        return None

    # Accept WebSocket
    await websocket.accept()

    # Store WebSocket reference in session
    session.websocket = websocket

    # Initialize services (Gmail, Gemini, etc.)
    # ...

# 3. Update disconnect() method to use safe_websocket_close
async def disconnect(self, user_id: str):
    session = voice_session_manager.get_cached_session(session_id)
    if session and session.websocket:
        await safe_websocket_close(session.websocket)

    # Clean up session
    await voice_session_manager.delete_session(session_id)

# 4. Add connection state checks before send operations
if is_websocket_connected(websocket):
    await websocket.send_json(data)
```

**Estimated Effort:** 2-3 hours

### Priority 2: Update Voice Controller for Session-Based WebSocket

**File**: `src/api/controllers/voice_controller.py`

**Current State:**
```python
@router.websocket("/voice")
async def voice_websocket_endpoint(websocket: WebSocket, firebase_user_id: str = Query(...)):
```

**Required Changes:**
```python
@router.websocket("/voice")
async def voice_websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(...),
    firebase_user_id: str = Query(...)
):
    """
    WebSocket endpoint for voice streaming.
    Requires a session_id created via POST /api/sessions.
    """
    # Validate session exists and is active
    session = await voice_session_manager.get_session(session_id)
    if not session or not session.active:
        await safe_websocket_close(websocket, code=1008, reason="Invalid or expired session")
        return

    # Validate session ownership
    if session.user_id != firebase_user_id:
        await safe_websocket_close(websocket, code=1008, reason="Unauthorized")
        return

    # Connect to voice handler
    user_id = await voice_handler.connect(websocket, firebase_user_id, session_id)
    # ...
```

**Estimated Effort:** 1 hour

### Priority 3: Update Function Handler for Async Session Manager

**File**: `src/core/voice/function_handler.py`

**Required Changes:**
All calls to `self.session` methods need `await`:

```python
# Before
session_state = self.session.get_session_state(self.user_id)
self.session.update_session_navigation(...)
self.session.store_current_message(...)

# After
session_state = await self.session.get_session_state(self.user_id)
await self.session.update_session_navigation(...)
await self.session.store_current_message(...)
```

**Files to Update:**
- `read_messages()` - 6 await calls
- `navigate_messages()` - 3 await calls
- `summarize_message()` - 2 await calls
- `mark_message()` - 1 await call
- `draft_email()` - 6 await calls for draft operations
- `_ensure_session_initialized()` - 2 await calls

**Estimated Effort:** 1-2 hours

## 📋 Detailed Migration Steps

### Step 1: Update voice_handler.py

1. **Import new modules:**
   ```python
   from ...core.session.voice_session_manager import voice_session_manager
   from ..websocket.websocket_helpers import safe_websocket_close, is_websocket_connected, send_json_safe
   ```

2. **Update connect() to use session manager:**
   - Remove `self.active_connections` dict
   - Load session from `voice_session_manager`
   - Validate session ownership
   - Store WebSocket and services in session object

3. **Update all send operations:**
   ```python
   # Replace
   await websocket.send_json(data)

   # With
   await send_json_safe(websocket, data)
   ```

4. **Update disconnect() for cleanup:**
   - Use `safe_websocket_close()`
   - Delete session from voice_session_manager
   - Clean up Gemini session

5. **Add proper task lifecycle:**
   ```python
   tasks = []
   try:
       task = asyncio.create_task(self._process_gemini_responses(...))
       tasks.append(task)
       await task
   finally:
       for task in tasks:
           if not task.done():
               task.cancel()
       await asyncio.gather(*tasks, return_exceptions=True)
   ```

### Step 2: Update voice_controller.py

1. **Change WebSocket route signature:**
   ```python
   @router.websocket("/voice")
   async def voice_websocket_endpoint(
       websocket: WebSocket,
       session_id: str = Query(...),
       firebase_user_id: str = Query(...)
   ):
   ```

2. **Add session validation:**
   ```python
   session = await voice_session_manager.get_session(session_id)
   if not session or not session.active:
       await safe_websocket_close(websocket, code=1008, reason="Invalid session")
       return

   if session.user_id != firebase_user_id:
       await safe_websocket_close(websocket, code=1008, reason="Unauthorized")
       return
   ```

3. **Pass session_id to handler:**
   ```python
   user_id = await voice_handler.connect(websocket, firebase_user_id, session_id)
   ```

### Step 3: Update function_handler.py

**Pattern to apply throughout:**

```python
# Find all calls to self.session methods
# Add await keyword

# Example fixes:
session_state = await self.session.get_session_state(self.user_id)
await self.session.update_session_navigation(self.user_id, ...)
await self.session.store_current_message(self.user_id, message, ttl=3600)
draft = await self.session.get_draft(self.user_id)
await self.session.store_draft(self.user_id, draft_data)
await self.session.clear_draft(self.user_id)
```

**Search and replace suggestions:**
```bash
# In function_handler.py, find these patterns and add await:
self.session.get_session_state(
self.session.update_session_navigation(
self.session.store_current_message(
self.session.get_current_message(
self.session.get_draft(
self.session.store_draft(
self.session.clear_draft(
self.session.get_or_init_session(
self.session.get_gemini_resumption_token(
self.session.store_gemini_resumption_token(
```

## 🧪 Testing Plan

### Unit Tests
1. Test async Redis operations
2. Test session creation and lifecycle
3. Test credential storage and refresh
4. Test Firebase async wrapper

### Integration Tests
1. **Session Flow:**
   - Create session via REST API
   - Connect WebSocket with session_id
   - Verify session validation
   - Delete session

2. **Voice Flow:**
   - Full voice conversation workflow
   - Message navigation
   - Draft creation
   - Error recovery

3. **Concurrent Sessions:**
   - Create multiple sessions per user
   - Test concurrent limit enforcement
   - Verify session isolation

### Load Tests
1. Multiple concurrent WebSocket connections
2. Redis connection pool under load
3. Session cleanup performance

## 🚀 Deployment Checklist

### Pre-Deployment
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Load tests complete
- [ ] Code review completed
- [ ] Documentation updated

### Deployment Steps
1. **Update dependencies:**
   ```bash
   pip install redis[asyncio]>=5.0.0
   ```

2. **Environment variables:**
   ```bash
   VOICE_SESSION_TTL=86400
   MAX_CONCURRENT_SESSIONS_PER_USER=3
   WS_CLOSE_TIMEOUT=5
   WS_PING_INTERVAL=30
   WS_PING_TIMEOUT=10
   ```

3. **Database migration:**
   - No schema changes required
   - Existing Redis data compatible
   - Sessions will auto-migrate on first access

4. **Rolling deployment:**
   - Deploy to staging first
   - Monitor Redis connections
   - Check WebSocket stability
   - Verify session persistence

### Post-Deployment
- [ ] Monitor Redis connection health
- [ ] Check WebSocket connection metrics
- [ ] Verify session cleanup running
- [ ] Monitor error rates
- [ ] Check Firebase async executor performance

## 📊 Performance Improvements Expected

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Redis Operations | Blocking | Async | ~50% faster |
| WebSocket Throughput | Limited | High | 2-3x |
| Connection Recovery | Manual | Automatic | 100% |
| Session Persistence | None | Redis | Infinite |
| Firebase Token Verify | Blocking | Async | ~30% faster |

## 🔍 Common Issues & Solutions

### Issue 1: "RuntimeError: No running event loop"
**Solution:** Ensure all async functions are called with `await` and from async context.

### Issue 2: Redis connection errors
**Solution:** Check Redis is running and `REDIS_HOST`/`REDIS_PORT` are correct. Automatic reconnection will handle transient failures.

### Issue 3: WebSocket close errors
**Solution:** Use `safe_websocket_close()` instead of direct `websocket.close()`.

### Issue 4: Session not found
**Solution:** Ensure client creates session via `POST /api/sessions` before connecting WebSocket.

## 📝 Code Review Checklist

- [ ] All `self.redis.*` calls have `await`
- [ ] All `self.session.*` calls have `await`
- [ ] All `credential_store.*` calls have `await`
- [ ] WebSocket operations use safe helpers
- [ ] Task lifecycle properly managed with try/finally
- [ ] Error logging uses logger, not print()
- [ ] Session validation in WebSocket endpoints
- [ ] Proper cleanup in finally blocks
- [ ] No synchronous blocking operations in async functions

## 🎯 Success Criteria

The migration is complete when:
1. All tests pass
2. No synchronous Redis operations remain
3. WebSocket connections stable under load
4. Sessions persist across server restarts
5. Automatic reconnection working
6. Background tasks running
7. No blocking I/O in async paths
8. Clean shutdown with no hanging tasks

## 📚 Additional Resources

- [Redis Async Documentation](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [Python Asyncio](https://docs.python.org/3/library/asyncio.html)
- [auto-translator-server](../auto-translator-server/) - Reference implementation
