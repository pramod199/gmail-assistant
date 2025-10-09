from pydantic import BaseModel, Field
from typing import Optional, Any


class UserConfigRequest(BaseModel):
    auto_mark_as_read: Optional[bool] = Field(None, description="Mark emails as read when reading them")
    auto_send_drafts: Optional[bool] = Field(None, description="Send drafts immediately vs save to Gmail")


class UserConfigResponse(BaseModel):
    auto_mark_as_read: bool
    auto_send_drafts: bool
    created_at: int
    updated_at: int


class DeleteConfigResponse(BaseModel):
    message: str
    user_id: str
    note: str


class ConfigValueResponse(BaseModel):
    key: str
    value: Any
    user_id: str
