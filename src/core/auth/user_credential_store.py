import json
from typing import Optional
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from ..session.redis_client import RedisClient
from ...models import GmailCredentials
from config import settings


class UserCredentialStore:
    """
    Redis-based storage for user-specific Gmail OAuth credentials
    Stores credentials using GmailCredentials model with automatic refresh handling
    """
    
    def __init__(self, redis_db: Optional[int] = None):
        self.redis_client = RedisClient(db=redis_db or settings.REDIS_DB)
    
    def _get_key(self, user_id: str) -> str:
        """Generate Redis key for user credentials"""
        return f"credentials:{user_id}"
    
    def store_credentials(self, user_id: str, credentials: Credentials) -> None:
        """
        Store user credentials in Redis using GmailCredentials model
        
        Args:
            user_id: Firebase user ID
            credentials: Google OAuth2 credentials
        """
        key = self._get_key(user_id)
        
        # Convert Google credentials to our model using SDK serialization
        gmail_creds = GmailCredentials.from_google_credentials(credentials)
        
        # Store with configured TTL
        self.redis_client.setex_json(
            key,
            settings.CREDENTIALS_TTL,
            gmail_creds.dict()
        )
    
    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """
        Retrieve and validate user credentials from Redis
        Automatically refreshes if needed
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Valid Google OAuth2 credentials or None if not found/invalid
        """
        key = self._get_key(user_id)
        cred_data = self.redis_client.get_json(key)
        
        if not cred_data:
            return None
        
        try:
            # Parse into our model
            gmail_creds = GmailCredentials(**cred_data)
            
            # Convert to Google credentials and refresh if needed
            credentials = gmail_creds.to_google_credentials()
            
            # Check if credentials need refresh using our model's method
            if gmail_creds.refresh_if_needed():
                # Store the refreshed credentials
                self.redis_client.setex_json(key, settings.CREDENTIALS_TTL, gmail_creds.dict())
                # Get the updated credentials
                credentials = gmail_creds.to_google_credentials()
            
            # Final validation
            if not credentials.valid and not credentials.refresh_token:
                self.remove_credentials(user_id)
                return None
                
            return credentials
            
        except Exception as e:
            print(f"Error parsing credentials for user {user_id}: {e}")
            self.remove_credentials(user_id)
            return None
    
    def get_gmail_credentials(self, user_id: str) -> Optional[GmailCredentials]:
        """
        Get GmailCredentials model directly
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            GmailCredentials model or None if not found
        """
        key = self._get_key(user_id)
        cred_data = self.redis_client.get_json(key)
        return GmailCredentials(**cred_data) if cred_data else None
    
    def store_gmail_credentials(self, user_id: str, credentials: GmailCredentials) -> None:
        """
        Store GmailCredentials model directly
        
        Args:
            user_id: Firebase user ID
            credentials: GmailCredentials model
        """
        key = self._get_key(user_id)
        self.redis_client.setex_json(key, settings.CREDENTIALS_TTL, credentials.dict())
    
    def remove_credentials(self, user_id: str) -> None:
        """
        Remove user credentials from Redis
        
        Args:
            user_id: Firebase user ID
        """
        key = self._get_key(user_id)
        self.redis_client.delete(key)
    
    def has_credentials(self, user_id: str) -> bool:
        """
        Check if user has stored credentials
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            True if credentials exist and are valid
        """
        gmail_creds = self.get_gmail_credentials(user_id)
        return gmail_creds is not None and gmail_creds.is_authorized and not gmail_creds.is_token_expired()