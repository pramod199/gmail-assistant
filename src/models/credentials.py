"""
Credentials Model for Gmail Assistant

Simple wrapper around Google OAuth2 credentials using SDK's native serialization.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


class GmailCredentials(BaseModel):
    """Gmail OAuth credentials using Google SDK's native serialization."""
    
    # Store Google credentials as serialized JSON dict
    google_credentials_json: Dict[str, Any] = Field(..., description="Google credentials as JSON dict")
    is_authorized: bool = Field(default=True, description="Whether OAuth is authorized")
    
    @classmethod
    def from_google_credentials(cls, credentials: Credentials) -> "GmailCredentials":
        """Create GmailCredentials from Google OAuth2 credentials."""
        return cls(
            google_credentials_json=credentials.to_json(),
            is_authorized=True
        )
    
    def to_google_credentials(self) -> Credentials:
        """Convert back to Google OAuth2 credentials."""
        return Credentials.from_authorized_user_info(self.google_credentials_json)
    
    def is_token_expired(self) -> bool:
        """Check if the access token is expired using Google SDK."""
        try:
            google_creds = self.to_google_credentials()
            return not google_creds.valid or google_creds.expired
        except Exception:
            return True
    
    def refresh_if_needed(self) -> bool:
        """Refresh credentials if needed using Google SDK."""
        try:
            google_creds = self.to_google_credentials()
            if not google_creds.valid and google_creds.refresh_token:
                google_creds.refresh(Request())
                # Update our stored credentials
                self.google_credentials_json = google_creds.to_json()
                return True
            return False
        except Exception:
            return False
    
    def revoke_authorization(self) -> None:
        """Revoke OAuth authorization."""
        self.is_authorized = False