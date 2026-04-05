"""
User Service - Local user management with Redis persistence
Automatically creates users on first Firebase authentication
"""

import logging
from typing import Optional
from datetime import datetime
from app.models.user import User
from app.services.redis_client import redis_service

logger = logging.getLogger(__name__)


class UserService:
    """
    Redis-based storage for local user records.
    Automatically creates users on first authentication.
    """

    def __init__(self):
        self.redis_client = redis_service

    async def get_user_key(self, user_id: str) -> str:
        """Generate Redis key for user."""
        return f"user:{user_id}"

    async def get_user_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """
        Get user by Firebase UID.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            User object or None if not found
        """
        user_key = await self.get_user_key(firebase_uid)
        user_data_json = await self.redis_client.get(user_key)

        if user_data_json:
            user = User.model_validate_json(user_data_json)
            logger.debug(f"Found existing user: {user.id}")
            return user
        return None

    async def create_user(self, firebase_uid: str, email: Optional[str] = None, auth_type: str = "firebase", api_key: Optional[str] = None) -> User:
        """
        Create a new user record.

        Args:
            firebase_uid: Firebase user ID or API key ID
            email: User email address
            auth_type: "firebase" or "apikey"
            api_key: API key if auth_type is "apikey"

        Returns:
            Created User object
        """
        user = User(
            id=firebase_uid,
            auth_type=auth_type,
            firebase_uid=firebase_uid if auth_type == "firebase" else None,
            api_key_origin=api_key if auth_type == "apikey" else None,
            email=email,
            created_at=datetime.utcnow(),
            login_count=1,
            last_login=datetime.utcnow()
        )

        # Store in Redis (no expiration - persist indefinitely)
        user_key = await self.get_user_key(firebase_uid)
        await self.redis_client.set_json(user_key, user.model_dump(mode='json'))

        logger.info(f"Created new user: {firebase_uid} ({email}) auth_type={auth_type}")
        return user

    async def update_login(self, firebase_uid: str) -> Optional[User]:
        """
        Update user's last login timestamp and increment login count.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            Updated User object or None if user not found
        """
        user = await self.get_user_by_firebase_uid(firebase_uid)
        if not user:
            logger.warning(f"Attempted to update login for non-existent user: {firebase_uid}")
            return None

        # Update login info
        user.last_login = datetime.utcnow()
        user.login_count += 1

        # Store back to Redis
        user_key = await self.get_user_key(firebase_uid)
        await self.redis_client.set_json(user_key, user.model_dump(mode='json'))

        logger.debug(f"Updated login for user {firebase_uid} (total logins: {user.login_count})")
        return user

    async def get_or_create_user_by_firebase_uid(
        self,
        firebase_uid: str,
        email: Optional[str] = None
    ) -> User:
        """
        Get existing user or create new one if doesn't exist.
        This is the main method used by authentication.

        Args:
            firebase_uid: Firebase user ID
            email: User email address

        Returns:
            User object (existing or newly created)
        """
        # Try to get existing user
        user = await self.get_user_by_firebase_uid(firebase_uid)

        if user:
            # User exists - update login info
            updated_user = await self.update_login(firebase_uid)
            return updated_user if updated_user else user

        # User doesn't exist - create new one
        logger.info(f"First time login detected for user {firebase_uid} ({email})")
        return await self.create_user(firebase_uid, email)

    async def update_email(self, firebase_uid: str, email: str) -> bool:
        """
        Update user's email address.

        Args:
            firebase_uid: Firebase user ID
            email: New email address

        Returns:
            True if updated successfully
        """
        user = await self.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return False

        if user.email == email:
            return True  # No change needed

        user.email = email

        user_key = await self.get_user_key(firebase_uid)
        await self.redis_client.set_json(user_key, user.model_dump(mode='json'))

        logger.info(f"Updated email for user {firebase_uid}: {email}")
        return True

    async def delete_user(self, firebase_uid: str) -> bool:
        """
        Delete user record.
        Note: This does NOT delete Firebase user, only local record.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            True if deleted successfully
        """
        user_key = await self.get_user_key(firebase_uid)
        deleted = await self.redis_client.delete(user_key)

        if deleted:
            logger.info(f"Deleted local user record: {firebase_uid}")

        return deleted > 0 if isinstance(deleted, int) else deleted


# Global singleton instance
user_service = UserService()
