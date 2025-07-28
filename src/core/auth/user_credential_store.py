import json
import redis
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


class UserCredentialStore:
    """
    Redis-based storage for user-specific Gmail OAuth credentials
    Stores credentials with automatic refresh handling
    """
    
    def __init__(self, redis_host: str = None, redis_port: int = None, redis_db: int = None):
        from ...config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
        
        self.redis_client = redis.Redis(
            host=redis_host or REDIS_HOST,
            port=redis_port or REDIS_PORT,
            db=redis_db or REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        self.key_prefix = "gmail_creds:"
    
    def _get_key(self, user_id: str) -> str:
        """Generate Redis key for user credentials"""
        return f"{self.key_prefix}{user_id}"
    
    def store_credentials(self, user_id: str, credentials: Credentials) -> None:
        """
        Store user credentials in Redis
        
        Args:
            user_id: Firebase user ID
            credentials: Google OAuth2 credentials
        """
        key = self._get_key(user_id)
        
        # Convert credentials to JSON
        cred_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "id_token": credentials.id_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        
        # Store with 7 day expiration (refresh tokens typically last longer)
        self.redis_client.setex(
            key, 
            7 * 24 * 60 * 60,  # 7 days in seconds
            json.dumps(cred_data)
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
        cred_json = self.redis_client.get(key)
        
        if not cred_json:
            return None
        
        try:
            cred_data = json.loads(cred_json)
            
            # Reconstruct credentials object
            credentials = Credentials(
                token=cred_data.get("token"),
                refresh_token=cred_data.get("refresh_token"),
                id_token=cred_data.get("id_token"),
                token_uri=cred_data.get("token_uri"),
                client_id=cred_data.get("client_id"),
                client_secret=cred_data.get("client_secret"),
                scopes=cred_data.get("scopes")
            )
            
            # Check if credentials are valid and refresh if needed
            if not credentials.valid:
                if credentials.expired and credentials.refresh_token:
                    try:
                        credentials.refresh(Request())
                        # Store the refreshed credentials
                        self.store_credentials(user_id, credentials)
                    except Exception as e:
                        print(f"Failed to refresh credentials for user {user_id}: {e}")
                        # Remove invalid credentials
                        self.remove_credentials(user_id)
                        return None
                else:
                    # No refresh token or other issue
                    self.remove_credentials(user_id)
                    return None
            
            return credentials
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing credentials for user {user_id}: {e}")
            self.remove_credentials(user_id)
            return None
    
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
        credentials = self.get_credentials(user_id)
        return credentials is not None and credentials.valid