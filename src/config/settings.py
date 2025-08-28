# Gmail Assistant Configuration Settings
import os

# Environment Detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Gemini LLM Configuration
GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_TEMPERATURE = 1
GEMINI_MAX_TOKENS = 1000
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here")

# Gmail Configuration
DEFAULT_EMAIL_LIMIT = 1
MAX_EMAIL_LIMIT = 20

# Message Display Configuration
DEFAULT_SNIPPET_LENGTH = 100
FULL_MESSAGE_KEYWORDS = ["full", "complete", "entire", "whole", "all"]
PREVIEW_KEYWORDS = ["preview", "snippet", "brief", "short"]

# Gmail Search Configuration
DEFAULT_QUERY = "is:unread -category:promotions -category:social"

# Application Configuration
APP_NAME = "Gmail Assistant"
APP_VERSION = "1.0.0"

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "./firebase-service-account.json")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Redis Database Selection
REDIS_DB_SESSIONS = int(os.getenv("REDIS_DB_SESSIONS", "0"))
REDIS_DB_DRAFTS = int(os.getenv("REDIS_DB_DRAFTS", "0"))
REDIS_DB_CREDENTIALS = int(os.getenv("REDIS_DB_CREDENTIALS", "0"))
NAVIGATION_KEY_PREFIX = "gmail_assistant:navigation"
NAVIGATION_TTL = 7 * 24 * 3600  # 7 days in seconds

# OAuth Configuration
OAUTH_REDIRECT_URI_DEV = "http://localhost:8000/api/auth/gmail/callback"
OAUTH_REDIRECT_URI_PROD = os.getenv("OAUTH_REDIRECT_URI_PROD", "https://yourdomain.com/api/auth/gmail/callback")

# Gmail OAuth Scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose"
]

# Security Configuration
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", "your_secret_key_for_oauth_state")

# Credentials Configuration
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "./credentials.json")