"""
Gmail Assistant Configuration Settings

Central configuration using pydantic_settings for type safety and validation.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application Configuration
    APP_NAME: str = "Gmail Assistant"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Gemini LLM Configuration
    GEMINI_MODEL: str = "gemini-2.5-flash-live-preview"
    GEMINI_TEMPERATURE: int = 1
    GEMINI_MAX_TOKENS: int = 1000
    GEMINI_API_KEY: str = ""
    
    # Gmail Configuration
    DEFAULT_EMAIL_LIMIT: int = 1
    MAX_EMAIL_LIMIT: int = 20
    GMAIL_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/gmail.modify"
    ]
    GMAIL_CREDENTIALS_FILE: str = "./credentials.json"
    
    # Message Display Configuration
    DEFAULT_SNIPPET_LENGTH: int = 100
    FULL_MESSAGE_KEYWORDS: List[str] = ["full", "complete", "entire", "whole", "all"]
    PREVIEW_KEYWORDS: List[str] = ["preview", "snippet", "brief", "short"]
    
    # Gmail Search Configuration
    DEFAULT_QUERY: str = "is:unread -category:promotions -category:social"
    
    # Firebase Configuration
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Redis TTL Settings (in seconds)
    USER_TTL: int = 7 * 24 * 3600  # 7 days for user data
    CREDENTIALS_TTL: int = 30 * 24 * 3600  # 30 days for OAuth tokens
    SESSION_TTL: int = 24 * 3600  # 24 hours for session data
    DRAFT_TTL: int = 7 * 24 * 3600  # 7 days for drafts
    
    # OAuth Configuration
    OAUTH_REDIRECT_URI_DEV: str = "http://localhost:8000/api/auth/gmail/callback"
    OAUTH_REDIRECT_URI_PROD: str = "https://yourdomain.com/api/auth/gmail/callback"
    OAUTH_STATE_SECRET: str = "your_secret_key_for_oauth_state"
    
    def get_oauth_redirect_uri(self) -> str:
        """Get the appropriate OAuth redirect URI based on environment."""
        if self.ENVIRONMENT == "production":
            return self.OAUTH_REDIRECT_URI_PROD
        return self.OAUTH_REDIRECT_URI_DEV
    
    def validate_gemini_config(self) -> bool:
        """Validate Gemini API configuration."""
        if not self.GEMINI_API_KEY or self.GEMINI_API_KEY == "your_gemini_api_key_here":
            return False
        return True
    
    def validate_firebase_config(self) -> bool:
        """Validate Firebase configuration."""
        return os.path.exists(self.FIREBASE_SERVICE_ACCOUNT_PATH)
    
    def validate_gmail_config(self) -> bool:
        """Validate Gmail OAuth configuration."""
        return os.path.exists(self.GMAIL_CREDENTIALS_FILE)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()