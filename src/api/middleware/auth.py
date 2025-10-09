import logging
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any

from ...config.settings import FIREBASE_SERVICE_ACCOUNT_PATH

logger = logging.getLogger(__name__)


def verify_firebase_token(token: str) -> Dict[str, Any]:
    """
    Core Firebase token validation logic extracted from middleware
    Returns user info or raises exception
    """
    try:
        # Ensure Firebase is initialized before token validation
        initialize_firebase()
        
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token.get("uid")
        user_email = decoded_token.get("email")
        
        if not user_id:
            logger.error("Firebase token missing user ID")
            raise HTTPException(
                status_code=401,
                detail="Invalid Firebase token: missing user ID"
            )
        
        logger.info(f"Firebase token verified for user: {user_id}")
        
        return {
            "user_id": user_id,
            "user_email": user_email,
            "firebase_token": decoded_token
        }
        
    except auth.InvalidIdTokenError as e:
        logger.error(f"Firebase ID token error: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Firebase ID token: {e.args[0] if e.args else 'Token validation failed'}"
        )


# Initialize Firebase Admin SDK
def initialize_firebase():
    if not firebase_admin._apps:
        try:
            # For production, use service account key file
            # For development, use GOOGLE_APPLICATION_CREDENTIALS env var
            if FIREBASE_SERVICE_ACCOUNT_PATH:
                cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized with service account")
            else:
                # Use default credentials (from GOOGLE_APPLICATION_CREDENTIALS)
                firebase_admin.initialize_app()
                logger.info("Firebase initialized with default credentials")
        except Exception as e:
            logger.error(f"Firebase initialization failed: {e}")
            logger.error("Cannot start application without proper Firebase configuration")
            raise RuntimeError(f"Firebase initialization failed: {e}") from e


async def firebase_auth_middleware(request: Request, call_next):
    """
    Firebase authentication middleware for FastAPI
    
    Skips auth for public endpoints (/, /health, /api/auth/*)
    For protected endpoints, validates Firebase ID token
    """
    
    # Skip auth for public endpoints
    public_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
    public_auth_paths = ["/api/auth/gmail/callback"]  # Only OAuth callback is public
    
    path = request.url.path
    
    # Allow public endpoints
    if path in public_paths:
        response = await call_next(request)
        return response
    
    # Allow only specific public auth endpoints (OAuth callback)
    if path in public_auth_paths:
        response = await call_next(request)
        return response
    
    # Validate Firebase token for protected endpoints
    try:
        logger.debug(f"Processing protected endpoint: {path}")
        
        # Extract Authorization header
        authorization = request.headers.get("Authorization")
        
        if not authorization:
            logger.debug("No authorization header found")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing"}
            )
        
        # Extract token from "Bearer <token>" format  
        logger.debug(f"Raw authorization header: '{authorization}'")
        try:
            parts = authorization.split(" ", 1)  # Split only once
            if len(parts) != 2:
                raise ValueError("Invalid authorization header format")
            scheme, token = parts
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authorization scheme")
        except ValueError as e:
            logger.debug(f"Auth format error: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"}
            )
        
        # Verify Firebase ID token using extracted utility
        logger.debug("Verifying Firebase token...")
        try:
            user_info = verify_firebase_token(token)
            user_id = user_info["user_id"]
            user_email = user_info["user_email"]
            decoded_token = user_info["firebase_token"]
            logger.debug(f"Token verified! User: {user_id}, Email: {user_email}")
        except HTTPException as e:
            # Convert HTTPException to JSONResponse to avoid Starlette error handling
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
            raise e

        # Get or create local user record
        try:
            from ...core.auth.user_store import user_store
            local_user = await user_store.get_or_create_user(user_id, user_email)
            logger.debug(f"Local user: {local_user.user_id} (logins: {local_user.login_count})")
        except Exception as e:
            logger.error(f"Failed to get/create local user: {e}")
            # Continue anyway - user store is not critical for authentication

        # Add user info to request state
        request.state.user_id = user_id
        request.state.user_email = user_email
        request.state.firebase_token = decoded_token
        
        logger.debug(f"Request state set: user_id={user_id}")
        
        # Continue to the next middleware/endpoint
        response = await call_next(request)
        return response
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal authentication error"}
        )


def get_current_user(request: Request) -> dict:
    """
    Dependency to get current authenticated user from request
    """
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=401,
            detail="User not authenticated"
        )
    
    return {
        "user_id": request.state.user_id,
        "user_email": request.state.user_email,
        "firebase_token": request.state.firebase_token
    }