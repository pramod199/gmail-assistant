# Gmail Assistant Configuration Settings

# Gemini LLM Configuration
GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_TEMPERATURE = 1
GEMINI_MAX_TOKENS = 1000

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

# Redis Configuration
import os
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
NAVIGATION_KEY_PREFIX = "gmail_assistant:navigation"
NAVIGATION_TTL = 7 * 24 * 3600  # 7 days in seconds