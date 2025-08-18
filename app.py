#!/usr/bin/env python3

import os
import sys
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.api.middleware.auth import firebase_auth_middleware
from src.api.controllers.gmail_controller import router as gmail_router
from src.api.controllers.auth_controller import router as auth_router
from src.api.controllers.voice_controller import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(gmail_router, prefix="/api/gmail", tags=["gmail"])
app.include_router(voice_router, prefix="/api/voice", tags=["voice"])


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