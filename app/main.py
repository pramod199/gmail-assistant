#!/usr/bin/env python3

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.utils.logging_config import setup_logging
from app.config import settings
from app.auth import initialize_firebase_app
from app.api.routes import router

# Set up logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info("🚀 Starting Gmail Assistant API...")

    # Initialize Firebase
    initialize_firebase_app()
    logger.info("✅ Firebase initialized")

    # Initialize Redis
    from app.services.redis_client import redis_service
    try:
        await redis_service.connect()
        logger.info("✅ Redis connected successfully")
    except ConnectionError as e:
        logger.critical(f"⚠️  Could not connect to Redis on startup: {e}")
        logger.warning("Application will continue but some features may not work")

    # Start background tasks
    from app.background_tasks import background_tasks
    await background_tasks.start()
    logger.info("✅ Background tasks started")

    yield

    # Shutdown
    logger.info("📴 Shutting down Gmail Assistant API...")

    # Stop background tasks
    await background_tasks.stop()
    logger.info("✅ Background tasks stopped")

    # Close Redis connection
    await redis_service.close()
    logger.info("✅ Redis connection closed")

    # Cleanup Firebase executor
    from app.services.firebase_async import cleanup_executor
    cleanup_executor()
    logger.info("✅ Firebase executor cleaned up")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Natural language voice interface for Gmail management with Firebase authentication.",
        version=settings.APP_VERSION,
        lifespan=lifespan,
        openapi_url="/openapi.json"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include main router
    app.include_router(router, prefix="/api")

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        }

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
        reload_dirs=["app"],
        log_level="info"
    )
