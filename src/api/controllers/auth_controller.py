from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from urllib.parse import urlencode
from pydantic import BaseModel
import hashlib
import secrets

from src.api.middleware.auth import get_current_user
from src.core.auth.user_credential_store import UserCredentialStore
from src.config.settings import (
    GMAIL_SCOPES, FRONTEND_URL, GMAIL_CREDENTIALS_FILE, 
    OAUTH_STATE_SECRET, ENVIRONMENT, OAUTH_REDIRECT_URI_DEV, OAUTH_REDIRECT_URI_PROD
)

router = APIRouter()

# Initialize credential store
credential_store = UserCredentialStore()


class GmailAuthStatus(BaseModel):
    is_authorized: bool
    user_id: str
    auth_url: str = None


@router.get("/gmail/status", response_model=GmailAuthStatus)
async def gmail_auth_status(request: Request, user: dict = Depends(get_current_user)):
    """
    Check if user has authorized Gmail access
    Returns auth URL if not authorized
    """
    user_id = user["user_id"]
    
    # Check if user has valid credentials
    has_creds = credential_store.has_credentials(user_id)
    
    if has_creds:
        return GmailAuthStatus(
            is_authorized=True,
            user_id=user_id
        )
    
    # Generate authorization URL
    auth_url = _generate_auth_url(user_id)
    
    return GmailAuthStatus(
        is_authorized=False,
        user_id=user_id,
        auth_url=auth_url
    )


@router.get("/gmail/authorize")
async def gmail_authorize(request: Request, user: dict = Depends(get_current_user)):
    """
    Start Gmail OAuth flow
    Redirects user to Google OAuth consent screen
    """
    user_id = user["user_id"]
    auth_url = _generate_auth_url(user_id)
    
    return RedirectResponse(url=auth_url)


@router.get("/gmail/callback")
async def gmail_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """
    Handle OAuth callback from Google
    Exchanges authorization code for credentials and stores them
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}"
        )
    
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code or state parameter"
        )
    
    try:
        # Validate state and extract user_id
        user_id = _validate_state(state)
        
        # Create flow and exchange code for credentials
        flow = _create_oauth_flow(request)
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Store credentials for user
        credential_store.store_credentials(user_id, credentials)
        
        # Return JSON success response (API-first approach)
        # TODO: When frontend is ready, uncomment below for frontend redirect:
        # return RedirectResponse(url=f"{FRONTEND_URL}/auth/success")
        return {
            "success": True,
            "message": "Gmail authorization successful",
            "user_id": user_id,
            "next_step": "You can now use Gmail API endpoints"
        }
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        # TODO: When frontend is ready, uncomment below for frontend redirect:
        # error_params = urlencode({"error": str(e)})
        # return RedirectResponse(url=f"{FRONTEND_URL}/auth/error?{error_params}")
        return {
            "success": False,
            "error": str(e),
            "message": "Gmail authorization failed"
        }


@router.delete("/gmail/revoke")
async def revoke_gmail_access(user: dict = Depends(get_current_user)):
    """
    Revoke Gmail access for current user
    Removes stored credentials
    """
    user_id = user["user_id"]
    credential_store.remove_credentials(user_id)
    
    return {"message": "Gmail access revoked successfully"}


def _create_oauth_flow() -> Flow:
    """Create OAuth flow with proper redirect URI"""
    import os
    
    if not os.path.exists(GMAIL_CREDENTIALS_FILE):
        raise HTTPException(
            status_code=500,
            detail="OAuth credentials file not found"
        )
    
    # Use appropriate redirect URI based on environment
    if ENVIRONMENT == "production":
        redirect_uri = OAUTH_REDIRECT_URI_PROD
    else:
        redirect_uri = OAUTH_REDIRECT_URI_DEV
    
    flow = Flow.from_client_secrets_file(
        GMAIL_CREDENTIALS_FILE,
        scopes=GMAIL_SCOPES,
        redirect_uri=redirect_uri
    )
    
    return flow


def _generate_auth_url(user_id: str) -> str:
    """Generate OAuth authorization URL with secure state"""
    flow = _create_oauth_flow()
    
    # Create secure state parameter with user_id and CSRF protection
    nonce = secrets.token_urlsafe(32)
    state_data = f"{user_id}:{nonce}"
    state_hash = hashlib.sha256(f"{state_data}:{OAUTH_STATE_SECRET}".encode()).hexdigest()
    secure_state = f"{state_data}:{state_hash}"
    
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=secure_state,
        prompt='consent'  # Force consent to ensure refresh token
    )
    
    return auth_url


def _validate_state(state: str) -> str:
    """Validate OAuth state parameter and return user_id"""
    try:
        parts = state.split(':')
        if len(parts) != 3:
            raise ValueError("Invalid state format")
        
        user_id, nonce, received_hash = parts
        expected_hash = hashlib.sha256(f"{user_id}:{nonce}:{OAUTH_STATE_SECRET}".encode()).hexdigest()
        
        if received_hash != expected_hash:
            raise ValueError("Invalid state hash")
        
        return user_id
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state parameter"
        )