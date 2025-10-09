import json
import asyncio
import logging
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from ..session.redis_client import redis_service
from ...config.settings import REDIS_DB_CREDENTIALS

logger = logging.getLogger(__name__)


class UserCredentialStore:
    """
    Redis-based storage for user-specific Gmail OAuth credentials (async version)
    Stores credentials with automatic refresh handling
    """

    def __init__(self, redis_db: Optional[int] = None):
        # Use a separate Redis client for credentials if different DB
        if redis_db and redis_db != redis_service._db:
            from ..session.redis_client import RedisClient
            self.redis_client = RedisClient(db=redis_db or REDIS_DB_CREDENTIALS)
        else:
            self.redis_client = redis_service
        self.key_prefix = "gmail_creds:"

    def _get_key(self, user_id: str) -> str:
        """Generate Redis key for user credentials"""
        return f"{self.key_prefix}{user_id}"
    
    async def store_credentials(self, user_id: str, credentials: Credentials) -> None:
        """
        Store user credentials in Redis using Google's built-in serialization

        Args:
            user_id: Firebase user ID
            credentials: Google OAuth2 credentials
        """
        key = self._get_key(user_id)

        # Use Google's built-in serialization - handles all fields automatically
        credentials_json = credentials.to_json()

        # Store with 30 day expiration (refresh tokens typically last longer)
        await self.redis_client.setex(
            key,
            credentials_json,
            30 * 24 * 60 * 60  # 30 days in seconds
        )
    
    async def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """
        Retrieve and validate user credentials from Redis
        Automatically refreshes if needed

        Args:
            user_id: Firebase user ID

        Returns:
            Valid Google OAuth2 credentials or None if not found/invalid
        """
        key = self._get_key(user_id)
        cred_json = await self.redis_client.get(key)

        if not cred_json:
            return None

        try:
            # Parse JSON data
            cred_data = json.loads(cred_json)

            # Use Google's built-in deserialization - handles all fields automatically
            credentials = Credentials.from_authorized_user_info(cred_data)

            # Check if credentials are valid and refresh if needed
            if not credentials.valid:
                if credentials.expired and credentials.refresh_token:
                    try:
                        # Run synchronous refresh in thread pool to avoid blocking
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            credentials.refresh,
                            Request()
                        )
                        # Store the refreshed credentials
                        await self.store_credentials(user_id, credentials)
                    except Exception as e:
                        logger.error(f"Failed to refresh credentials for user {user_id}: {e}")
                        # Remove invalid credentials
                        await self.remove_credentials(user_id)
                        return None
                else:
                    # No refresh token or other issue
                    await self.remove_credentials(user_id)
                    return None

            return credentials

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing credentials for user {user_id}: {e}")
            await self.remove_credentials(user_id)
            return None
    
    async def remove_credentials(self, user_id: str) -> None:
        """
        Remove user credentials from Redis

        Args:
            user_id: Firebase user ID
        """
        key = self._get_key(user_id)
        await self.redis_client.delete(key)

    async def has_credentials(self, user_id: str) -> bool:
        """
        Check if user has stored credentials

        Args:
            user_id: Firebase user ID

        Returns:
            True if credentials exist and are valid
        """
        credentials = await self.get_credentials(user_id)
        return credentials is not None and credentials.valid