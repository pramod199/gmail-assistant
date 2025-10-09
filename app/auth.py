import logging
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import HTTPException, Request, Depends, Query, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

# Firebase initialization flag
_firebase_app_initialized = False

# HTTP Bearer scheme for dependency injection
firebase_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Optional[dict]:
    """Verify API key from X-API-Key header."""
    if not x_api_key:
        return None

    if not settings.FIREBASE_WEB_API_KEY:
        return None

    # Check if the provided API key matches
    if x_api_key == settings.FIREBASE_WEB_API_KEY:
        # Return a dict with API key info
        return {
            "uid": f"apikey:{x_api_key[:8]}",  # Use first 8 chars as identifier
            "auth_type": "apikey",
            "api_key": x_api_key
        }

    return None


def initialize_firebase_app():
    """Initialize Firebase Admin SDK."""
    global _firebase_app_initialized
    if not _firebase_app_initialized:
        if settings.FIREBASE_SERVICE_ACCOUNT_PATH:
            try:
                cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(cred)
                _firebase_app_initialized = True
                logger.info("Firebase Admin SDK initialized successfully from path.")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK from path: {e}")
                raise RuntimeError(f"Firebase initialization failed: {e}") from e
        else:
            logger.warning("Firebase service account key not configured. Firebase auth will not work.")


async def verify_firebase_token(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(firebase_bearer_scheme)
) -> Optional[dict]:
    """Verify Firebase ID token from Bearer token."""
    if not _firebase_app_initialized:
        return None  # Firebase not set up

    if auth_credentials is None or auth_credentials.scheme.lower() != "bearer":
        return None  # Not a Bearer token

    token = auth_credentials.credentials
    try:
        # Import async wrapper
        from app.services.firebase_async import verify_id_token_async
        decoded_token = await verify_id_token_async(token)
        return decoded_token
    except firebase_auth.FirebaseError as e:
        logger.warning(f"Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Firebase Token: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during Firebase token verification: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error verifying Firebase token"
        )


async def get_current_user(
    firebase_claims: Optional[dict] = Depends(verify_firebase_token),
    api_key_claims: Optional[dict] = Depends(verify_api_key)
) -> User:
    """
    Unified authentication dependency for HTTP endpoints.
    Supports both Firebase token and API key authentication.
    Returns authenticated User model.
    """
    # Try API key first (simpler for testing)
    if api_key_claims:
        uid = api_key_claims.get("uid")
        api_key = api_key_claims.get("api_key")

        # Import user service to get or create user
        from app.services.user_service import user_service
        user = await user_service.get_user_by_firebase_uid(uid)

        if not user:
            # Create new API key user
            user = await user_service.create_user(
                firebase_uid=uid,
                email=None,
                auth_type="apikey",
                api_key=api_key
            )
        else:
            # Update login
            await user_service.update_login(uid)
            user = await user_service.get_user_by_firebase_uid(uid)

        logger.debug(f"Authenticated user {user.id} via API key.")
        return user

    # Try Firebase authentication
    if firebase_claims:
        uid = firebase_claims.get("uid")
        email = firebase_claims.get("email")
        if not uid:
            raise HTTPException(status_code=401, detail="Firebase token missing UID.")

        # Import user service to get or create user
        from app.services.user_service import user_service
        user = await user_service.get_or_create_user_by_firebase_uid(uid, email)
        logger.debug(f"Authenticated user {user.id} via Firebase.")
        return user

    # If both methods failed
    raise HTTPException(
        status_code=401,
        detail="Not authenticated. Provide Firebase token in Authorization header or API key in X-API-Key header."
    )


async def authenticate_websocket_user(
    token: Optional[str] = Query(None, description="Firebase ID Token")
) -> User:
    """
    Authenticates a WebSocket connection using Firebase token passed as query parameter.
    Returns authenticated User model.
    """
    if token:
        if not _firebase_app_initialized:
            raise HTTPException(
                status_code=1008,  # WS_1008_POLICY_VIOLATION
                detail="Firebase auth not configured on server."
            )
        try:
            from app.services.firebase_async import verify_id_token_async
            decoded_token = await verify_id_token_async(token)
            uid = decoded_token.get("uid")
            email = decoded_token.get("email")
            if not uid:
                raise HTTPException(status_code=1008, detail="Firebase token missing UID.")

            from app.services.user_service import user_service
            user = await user_service.get_or_create_user_by_firebase_uid(uid, email)
            logger.debug(f"Authenticated WebSocket user {user.id} via Firebase token.")
            return user
        except firebase_auth.FirebaseError as e:
            logger.warning(f"WebSocket Firebase token verification failed: {e}")
            raise HTTPException(status_code=1008, detail=f"Invalid Firebase Token: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket Firebase token verification: {e}")
            raise HTTPException(status_code=1008, detail="Error verifying Firebase token")

    raise HTTPException(
        status_code=1008,
        detail="Authentication required. Provide 'token' (Firebase) query parameter."
    )
