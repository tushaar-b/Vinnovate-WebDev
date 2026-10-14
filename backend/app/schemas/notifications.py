import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


def mask_secret(value: Optional[str]) -> Optional[str]:
    """Masks sensitive secret tokens, webhooks, or passwords."""
    if not value:
        return ""
    val_str = str(value).strip()
    if len(val_str) <= 6:
        return "******"
    if "discord.com/api/webhooks" in val_str:
        # e.g. https://discord.com/api/webhooks/123456/abcdef...
        parts = val_str.split("/")
        if len(parts) >= 2:
            return "/".join(parts[:-1]) + "/******"
    return val_str[:4] + "******" + val_str[-3:]


def sanitize_channel_config(channel_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a sanitized configuration dictionary with secrets masked."""
    sanitized = dict(config)
    ch_type = channel_type.lower()
    if ch_type == "discord":
        if "webhook_url" in sanitized and sanitized["webhook_url"]:
            sanitized["webhook_url"] = mask_secret(sanitized["webhook_url"])
    elif ch_type == "telegram":
        if "bot_token" in sanitized and sanitized["bot_token"]:
            sanitized["bot_token"] = mask_secret(sanitized["bot_token"])
    elif ch_type == "email":
        if "smtp_password" in sanitized and sanitized["smtp_password"]:
            sanitized["smtp_password"] = mask_secret(sanitized["smtp_password"])
    return sanitized


class NotificationChannelConfigPayload(BaseModel):
    enabled: bool = True
    configuration: Dict[str, Any] = Field(default_factory=dict)


class NotificationChannelResponse(BaseModel):
    id: uuid.UUID
    monitor_id: Optional[uuid.UUID] = None
    channel_type: str
    enabled: bool
    configuration: Dict[str, Any]
    created_at: datetime


class NotificationSettingsResponse(BaseModel):
    channels: Dict[str, NotificationChannelResponse]


class TestNotificationRequest(BaseModel):
    configuration: Optional[Dict[str, Any]] = None


class TestNotificationResponse(BaseModel):
    success: bool
    message: str
    channel_type: str


class NotificationOutboxItemResponse(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    monitor_name: Optional[str] = None
    monitor_url: Optional[str] = None
    version_id: uuid.UUID
    channel_id: uuid.UUID
    channel_type: str
    state: str
    attempts: int
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
