from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with Pydantic validation."""

    # Application Configuration
    APP_NAME: str = "Gmail Assistant"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # Firebase Configuration
    FIREBASE_SERVICE_ACCOUNT_PATH: Optional[str] = "./firebase-service-account.json"
    FIREBASE_WEB_API_KEY: Optional[str] = None

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Redis Database Selection
    REDIS_DB_SESSIONS: int = 0
    REDIS_DB_DRAFTS: int = 0
    REDIS_DB_CREDENTIALS: int = 0
    NAVIGATION_KEY_PREFIX: str = "gmail_assistant:navigation"
    NAVIGATION_TTL: int = 7 * 24 * 3600  # 7 days in seconds

    # Gmail Configuration
    DEFAULT_EMAIL_LIMIT: int = 1
    MAX_EMAIL_LIMIT: int = 20
    DEFAULT_SNIPPET_LENGTH: int = 100
    DEFAULT_QUERY: str = "is:unread -category:promotions -category:social"

    # Message Display Configuration
    FULL_MESSAGE_KEYWORDS: List[str] = ["full", "complete", "entire", "whole", "all"]
    PREVIEW_KEYWORDS: List[str] = ["preview", "snippet", "brief", "short"]

    # Gmail OAuth Configuration
    GMAIL_CREDENTIALS_FILE: str = "./credentials.json"
    GMAIL_SCOPES: List[str] = [
        "https://www.googleapis.com/auth/gmail.modify",
    ]
    OAUTH_REDIRECT_URI_DEV: str = "http://localhost:8000/api/auth/gmail/callback"
    OAUTH_REDIRECT_URI_PROD: str = "https://yourdomain.com/api/auth/gmail/callback"
    OAUTH_STATE_SECRET: str = "your_secret_key_for_oauth_state"

    # Gemini API Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-pro"
    GEMINI_FLASH_LITE_MODEL: str = "gemini-3.1-flash-lite-preview"
    GEMINI_TEMPERATURE: int = 1
    GEMINI_MAX_TOKENS: int = 1000
    GEMINI_HTTP_TIMEOUT: int = 300000  # HTTP timeout in milliseconds (default: 5 minutes)

    # Voice Session Configuration
    VOICE_SESSION_TTL: int = 86400  # 24 hours
    MAX_CONCURRENT_SESSIONS_PER_USER: int = 3

    # WebSocket Configuration
    WS_CLOSE_TIMEOUT: int = 5  # seconds
    WS_PING_INTERVAL: int = 30  # seconds
    WS_PING_TIMEOUT: int = 10  # seconds

    class Config:
        env_file = ".env"


settings = Settings()
