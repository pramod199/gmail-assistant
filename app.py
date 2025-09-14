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
    yield
    # Shutdown
    print("📴 Shutting down Gmail Assistant API...")


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