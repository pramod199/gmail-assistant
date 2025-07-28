import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Request
from typing import Optional


# Initialize Firebase Admin SDK
def initialize_firebase():
    if not firebase_admin._apps:
        try:
            from ...config.settings import FIREBASE_SERVICE_ACCOUNT_PATH
            
            # For production, use service account key file
            # For development, use GOOGLE_APPLICATION_CREDENTIALS env var
            if FIREBASE_SERVICE_ACCOUNT_PATH:
                cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(cred)
            else:
                # Use default credentials (from GOOGLE_APPLICATION_CREDENTIALS)
                firebase_admin.initialize_app()
        except Exception as e:
            print(f"Warning: Firebase initialization failed: {e}")
            print("Firebase authentication will not work without proper configuration")


async def firebase_auth_middleware(request: Request, call_next):
    """
    Firebase authentication middleware for FastAPI
    
    Skips auth for public endpoints (/, /health, /api/auth/*)
    For protected endpoints, validates Firebase ID token
    """
    
    # Initialize Firebase if not already done
    initialize_firebase()
    
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
        print(f"DEBUG: Processing protected endpoint: {path}")
        
        # Extract Authorization header
        authorization = request.headers.get("Authorization")
        print(f"DEBUG: Auth header present: {authorization is not None}")
        
        if not authorization:
            print("DEBUG: No authorization header found")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing"}
            )
        
        # Extract token from "Bearer <token>" format  
        print(f"DEBUG: Raw authorization header: '{authorization}'")
        try:
            parts = authorization.split(" ", 1)  # Split only once
            print(f"DEBUG: Split parts: {len(parts)}, Parts: {parts}")
            if len(parts) != 2:
                raise ValueError("Invalid authorization header format")
            scheme, token = parts
            print(f"DEBUG: Scheme: '{scheme}', Token length: {len(token)}")
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authorization scheme")
        except ValueError as e:
            print(f"DEBUG: Auth format error: {e}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"}
            )
        
        # Verify Firebase ID token
        print(f"DEBUG: Verifying Firebase token...")
        print(f"DEBUG: Token starts with: {token[:50]}...")
        try:
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token.get("uid")
            user_email = decoded_token.get("email")
            print(f"DEBUG: Token verified! User: {user_id}, Email: {user_email}")
        except Exception as token_error:
            print(f"DEBUG: Token verification failed: {token_error}")
            print(f"DEBUG: Token type: {type(token)}")
            print(f"DEBUG: Token length: {len(token)}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Firebase ID token"}
            )
        
        # Add user info to request state
        request.state.user_id = user_id
        request.state.user_email = user_email
        request.state.firebase_token = decoded_token
        
        print(f"DEBUG: Request state set: user_id={user_id}")
        
        # Continue to the next middleware/endpoint
        response = await call_next(request)
        return response
        
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Firebase ID token"
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        print(f"Authentication error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal authentication error"
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