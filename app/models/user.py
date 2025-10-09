from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class User(BaseModel):
    """User domain model - single source of truth."""
    id: str  # Unique identifier (Firebase UID or "apikey:<API_KEY_VALUE>")
    auth_type: Literal["firebase", "apikey"] = "firebase"
    firebase_uid: Optional[str] = None
    api_key_origin: Optional[str] = None  # Stores the API key if auth_type is apikey
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    login_count: int = 0
    last_login: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
