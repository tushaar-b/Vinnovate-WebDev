import re
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


def mask_secret(value: Optional[str]) -> Optional[str]:
    """Masks sensitive secret tokens, webhooks, or passwords."""
    if not value:
        return ""
    val_str = str(value).strip()
    if not val_str:
        return ""
    if len(val_str) <= 6:
        return "******"

    # Discord webhook URLs: e.g. https://discord.com/api/webhooks/<id>/<token>
    # Mask the webhook token across all official Discord domains and trailing slash/queries
    discord_match = re.match(
        r'^(https?://[^/]+/api/webhooks/[^/?#]+/)[^/?#]+.*$',
        val_str,
        re.IGNORECASE,
    )
    if discord_match:
        return f"{discord_match.group(1)}******"

    if "/api/webhooks/" in val_str:
        clean = val_str.rstrip("/")
        parts = clean.split("/")
        if len(parts) >= 2:
            return "/".join(parts[:-1]) + "/******"

    # Telegram bot tokens: preserve bot ID, mask secret token portion
    if ":" in val_str and not val_str.startswith("http"):
        parts = val_str.split(":", 1)
        return f"{parts[0]}:******"

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

    @field_validator("last_error", mode="before")
    @classmethod
    def sanitize_err(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        from app.services.security import sanitize_error_message
        return sanitize_error_message(v)


# -------------------------------------------------------------------------
# Judge Workspace Notification Schemas
# -------------------------------------------------------------------------
class JudgeNotificationChannelPayload(BaseModel):
    monitor_id: uuid.UUID
    configuration: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class JudgeTestNotificationRequest(BaseModel):
    monitor_id: uuid.UUID
    configuration: Optional[Dict[str, Any]] = None


class JudgeTestNotificationResponse(BaseModel):
    success: bool
    message: str
    channel_type: str
    verification_required: bool = True
    verification_code: Optional[str] = None


class JudgeVerifyChannelRequest(BaseModel):
    monitor_id: uuid.UUID
    code: str


class JudgeNotificationChannelResponse(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    monitor_name: Optional[str] = None
    channel_type: str
    enabled: bool
    is_verified: bool
    configuration: Dict[str, Any]
    created_at: datetime


class JudgeNotificationSettingsResponse(BaseModel):
    channels: Dict[str, Optional[JudgeNotificationChannelResponse]]
    limits: Dict[str, Any]

