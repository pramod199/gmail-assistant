from fastapi import APIRouter
from app.routers import (
    auth_router,
    user_router,
    sessions_router,
    voice_router,
    config_router,
    health_router
)

# Create main router
router = APIRouter()

# Include all sub-routers with appropriate prefixes and tags
router.include_router(auth_router, prefix="/auth", tags=["authentication"])
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
router.include_router(voice_router, tags=["websocket"])  # No prefix - endpoint is /ws/{session_id}
router.include_router(config_router, prefix="/config", tags=["configuration"])
router.include_router(health_router, tags=["health"])
