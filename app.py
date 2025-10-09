#!/usr/bin/env python3

import os
import sys
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config.logging_config import setup_logging
from src.api.middleware.auth import firebase_auth_middleware

from src.api.controllers.auth_controller import router as auth_router
from src.api.controllers.voice_controller import router as voice_router
from src.api.controllers.config_controller import router as config_router
from src.api.controllers.session_controller import router as session_router
from src.api.controllers.user_controller import router as user_router
from src.api.handlers.exception_handler import (
    http_exception_handler,
    firebase_auth_exception_handler, 
    general_exception_handler
)
from firebase_admin.auth import InvalidIdTokenError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    print("🚀 Starting Gmail Assistant API...")

    # Import services
    from src.core.session.redis_client import redis_service
    from src.core.background_tasks import background_tasks
    from src.core.auth.firebase_async import cleanup_executor

    # Initialize Redis
    try:
        await redis_service.connect()
        print("✅ Redis connected successfully")
    except ConnectionError as e:
        print(f"⚠️  Could not connect to Redis on startup: {e}")
        print("   Application will continue but some features may not work")

    # Start background tasks
    await background_tasks.start()
    print("✅ Background tasks started")

    yield

    # Shutdown
    print("📴 Shutting down Gmail Assistant API...")

    # Stop background tasks
    await background_tasks.stop()
    print("✅ Background tasks stopped")

    # Close Redis connection
    await redis_service.close()
    print("✅ Redis connection closed")

    # Cleanup Firebase executor
    cleanup_executor()
    print("✅ Firebase executor cleaned up")


app = FastAPI(
    title="Gmail Assistant API",
    description="Natural language interface for Gmail management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase auth middleware
app.middleware("http")(firebase_auth_middleware)

# Register exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(InvalidIdTokenError, firebase_auth_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(user_router, prefix="/api/users", tags=["users"])
app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
app.include_router(config_router, prefix="/api/config", tags=["configuration"])


@app.get("/")
async def root():
    return {"message": "Gmail Assistant API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from src.config.settings import API_HOST, API_PORT, ENVIRONMENT
    
    uvicorn.run(
        "app:app",
        host=API_HOST,
        port=API_PORT,
        reload=ENVIRONMENT == "development",
        log_level="info"
    )