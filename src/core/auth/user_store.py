"""
User Store - Local user management with Redis persistence
Automatically creates users on first Firebase authentication
"""

import logging
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from ..session.redis_client import redis_service

logger = logging.getLogger(__name__)


class User(BaseModel):
    """Local user model"""
    user_id: str  # Firebase UID
    email: str
    created_at: int  # Unix timestamp
    updated_at: int  # Unix timestamp
    last_login: int  # Unix timestamp
    login_count: int = 0


class UserStore:
    """
    Redis-based storage for local user records
    Automatically creates users on first authentication
    """

    def __init__(self):
        self.redis_client = redis_service
        self.key_prefix = "user:"

    def _get_key(self, user_id: str) -> str:
        """Generate Redis key for user"""
        return f"{self.key_prefix}{user_id}"

    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Get user by Firebase UID

        Args:
            user_id: Firebase user ID

        Returns:
            User object or None if not found
        """
        key = self._get_key(user_id)
        user_data = await self.redis_client.get_json(key)

        if not user_data:
            return None

        try:
            return User(**user_data)
        except Exception as e:
            logger.error(f"Error parsing user data for {user_id}: {e}")
            return None

    async def create_user(self, user_id: str, email: str) -> User:
        """
        Create a new user record

        Args:
            user_id: Firebase user ID
            email: User email address

        Returns:
            Created User object
        """
        now = int(time.time())

        user = User(
            user_id=user_id,
            email=email,
            created_at=now,
            updated_at=now,
            last_login=now,
            login_count=1
        )

        # Store in Redis (no expiration - persist indefinitely)
        key = self._get_key(user_id)
        await self.redis_client.set_json(key, user.model_dump())

        logger.info(f"Created new user: {user_id} ({email})")
        return user

    async def update_login(self, user_id: str) -> bool:
        """
        Update user's last login timestamp and increment login count

        Args:
            user_id: Firebase user ID

        Returns:
            True if updated successfully
        """
        user = await self.get_user(user_id)
        if not user:
            logger.warning(f"Attempted to update login for non-existent user: {user_id}")
            return False

        # Update login info
        user.last_login = int(time.time())
        user.login_count += 1
        user.updated_at = int(time.time())

        # Store back to Redis
        key = self._get_key(user_id)
        await self.redis_client.set_json(key, user.model_dump())

        logger.debug(f"Updated login for user {user_id} (total logins: {user.login_count})")
        return True

    async def get_or_create_user(self, user_id: str, email: str) -> User:
        """
        Get existing user or create new one if doesn't exist
        This is the main method used by authentication middleware

        Args:
            user_id: Firebase user ID
            email: User email address

        Returns:
            User object (existing or newly created)
        """
        # Try to get existing user
        user = await self.get_user(user_id)

        if user:
            # User exists - update login info
            await self.update_login(user_id)
            return user

        # User doesn't exist - create new one
        logger.info(f"First time login detected for user {user_id} ({email})")
        return await self.create_user(user_id, email)

    async def update_email(self, user_id: str, email: str) -> bool:
        """
        Update user's email address
        Useful if email changes in Firebase

        Args:
            user_id: Firebase user ID
            email: New email address

        Returns:
            True if updated successfully
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        if user.email == email:
            return True  # No change needed

        user.email = email
        user.updated_at = int(time.time())

        key = self._get_key(user_id)
        await self.redis_client.set_json(key, user.model_dump())

        logger.info(f"Updated email for user {user_id}: {email}")
        return True

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user record
        Note: This does NOT delete Firebase user, only local record

        Args:
            user_id: Firebase user ID

        Returns:
            True if deleted successfully
        """
        key = self._get_key(user_id)
        deleted = await self.redis_client.delete(key)

        if deleted:
            logger.info(f"Deleted local user record: {user_id}")

        return deleted

    async def get_user_count(self) -> int:
        """
        Get total number of users in system

        Returns:
            Total user count
        """
        pattern = f"{self.key_prefix}*"
        keys = await self.redis_client.keys(pattern)
        return len(keys)


# Global singleton instance
user_store = UserStore()
