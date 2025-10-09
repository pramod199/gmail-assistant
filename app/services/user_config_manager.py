from typing import Dict, Any, Optional
import time
import logging
from app.services.redis_client import RedisClient

logger = logging.getLogger(__name__)


class UserConfigManager:
    """Manage user-specific configuration settings"""
    
    def __init__(self):
        self.redis = RedisClient()
    
    def _get_config_key(self, firebase_uid: str) -> str:
        """Generate Redis key for user configuration"""
        return f"user_config:{firebase_uid}"
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default user configuration"""
        return {
            "auto_mark_as_read": True,    # Mark emails as read when reading them
            "auto_send_drafts": False,    # Send drafts immediately vs save to Gmail
            "created_at": int(time.time()),
            "updated_at": int(time.time())
        }
    
    def get_config(self, firebase_uid: str) -> Dict[str, Any]:
        """
        Get user configuration with defaults
        
        Args:
            firebase_uid: User identifier
            
        Returns:
            User configuration dictionary with default values if not found
        """
        try:
            key = self._get_config_key(firebase_uid)
            config = self.redis.get_json(key)
            
            if config is None:
                # Return defaults if no config exists
                logger.debug(f"No config found for user {firebase_uid}, returning defaults")
                return self._get_default_config()
            
            # Ensure all default keys exist (for backward compatibility)
            default_config = self._get_default_config()
            for key_name, default_value in default_config.items():
                if key_name not in config and key_name not in ["created_at", "updated_at"]:
                    config[key_name] = default_value
            
            logger.debug(f"Retrieved config for user {firebase_uid}: {config}")
            return config
            
        except Exception as e:
            logger.error(f"Error getting config for user {firebase_uid}: {e}")
            return self._get_default_config()
    
    def set_config(self, firebase_uid: str, config: Dict[str, Any], ttl: int = 7776000) -> bool:
        """
        Set complete user configuration
        
        Args:
            firebase_uid: User identifier
            config: Complete configuration dictionary
            ttl: Time to live in seconds (default: 90 days)
            
        Returns:
            True if successfully stored
        """
        try:
            # Ensure required timestamps
            config["updated_at"] = int(time.time())
            if "created_at" not in config:
                config["created_at"] = int(time.time())
            
            key = self._get_config_key(firebase_uid)
            success = self.redis.setex_json(key, ttl, config)
            
            if success:
                logger.info(f"Stored config for user {firebase_uid}")
            else:
                logger.error(f"Failed to store config for user {firebase_uid}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting config for user {firebase_uid}: {e}")
            return False
    
    def update_config(self, firebase_uid: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific configuration fields
        
        Args:
            firebase_uid: User identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if successfully updated
        """
        try:
            # Get existing config or defaults
            current_config = self.get_config(firebase_uid)
            
            # Apply updates
            current_config.update(updates)
            current_config["updated_at"] = int(time.time())
            
            # Store updated config
            return self.set_config(firebase_uid, current_config)
            
        except Exception as e:
            logger.error(f"Error updating config for user {firebase_uid}: {e}")
            return False
    
    def delete_config(self, firebase_uid: str) -> bool:
        """
        Delete user configuration
        
        Args:
            firebase_uid: User identifier
            
        Returns:
            True if successfully deleted
        """
        try:
            key = self._get_config_key(firebase_uid)
            success = self.redis.delete(key)
            
            if success:
                logger.info(f"Deleted config for user {firebase_uid}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting config for user {firebase_uid}: {e}")
            return False
    
    def get_config_value(self, firebase_uid: str, key: str, default: Any = None) -> Any:
        """
        Get specific configuration value
        
        Args:
            firebase_uid: User identifier
            key: Configuration key to retrieve
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            config = self.get_config(firebase_uid)
            return config.get(key, default)
            
        except Exception as e:
            logger.error(f"Error getting config value {key} for user {firebase_uid}: {e}")
            return default