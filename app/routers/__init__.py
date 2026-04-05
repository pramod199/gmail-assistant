from .auth import router as auth_router
from .user import router as user_router
from .sessions import router as sessions_router
from .voice import router as voice_router
from .config import router as config_router
from .health import router as health_router

__all__ = [
    'auth_router',
    'user_router',
    'sessions_router',
    'voice_router',
    'config_router',
    'health_router'
]
