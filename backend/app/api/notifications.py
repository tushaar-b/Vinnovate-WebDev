import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    NotificationChannel,
    NotificationOutbox,
    Monitor,
    ChannelTypeEnum,
    OutboxStateEnum,
    utc_now,
)
from app.schemas.notifications import (
    NotificationChannelConfigPayload,
    NotificationChannelResponse,
    NotificationSettingsResponse,
    TestNotificationRequest,
    TestNotificationResponse,
    NotificationOutboxItemResponse,
    sanitize_channel_config,
)
from app.services.notifier import send_test_notification
from app.services.security import (
    sanitize_error_message,
    encrypt_channel_config,
    decrypt_channel_config,
    validate_discord_webhook_url,
    validate_telegram_config,
)

router = APIRouter(tags=["notifications"])


def get_or_create_global_channel(
    db: Session, channel_type: str
) -> NotificationChannel:
    """Finds or creates global notification channel record."""
    ch_enum = ChannelTypeEnum(channel_type.lower())
    channel = (
        db.query(NotificationChannel)
        .filter(
            NotificationChannel.monitor_id.is_(None),
            NotificationChannel.channel_type == ch_enum,
        )
        .first()
    )
    if not channel:
        channel = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=None,
            channel_type=ch_enum,
            configuration_json={},
            enabled=False,
            created_at=utc_now(),
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
    return channel


@router.get("/settings/notifications", response_model=Dict[str, NotificationChannelResponse])
def get_notification_settings(db: Session = Depends(get_db)):
    """Returns global notification channels with credentials decrypted then securely masked."""
    result = {}
    for ch_type in ["discord", "telegram", "email"]:
        ch = get_or_create_global_channel(db, ch_type)
        decrypted_cfg = decrypt_channel_config(ch_type, ch.configuration_json or {})
        sanitized_cfg = sanitize_channel_config(ch_type, decrypted_cfg)
        result[ch_type] = NotificationChannelResponse(
            id=ch.id,
            monitor_id=ch.monitor_id,
            channel_type=ch_type,
            enabled=ch.enabled,
            configuration=sanitized_cfg,
            created_at=ch.created_at,
        )
    return result


@router.put("/settings/notifications/{channel_type}", response_model=NotificationChannelResponse)
def update_notification_settings(
    channel_type: str,
    payload: NotificationChannelConfigPayload,
    db: Session = Depends(get_db),
):
    """
    Updates configuration and toggle for global notification channel.
    - Preserves existing secrets if updated configuration supplies a masked or blank secret.
    - Validates destination URLs and token formats.
    - Encrypts credentials at rest with authenticated AES encryption before database persistence.
    """
    ch_type = channel_type.lower()
    if ch_type not in ["discord", "telegram", "email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CHANNEL", "message": f"Unsupported channel {channel_type}"}},
        )

    channel = get_or_create_global_channel(db, ch_type)
    existing_cfg = decrypt_channel_config(ch_type, channel.configuration_json or {})
    new_cfg = dict(payload.configuration or {})

    # Merge secrets safely: do not overwrite real secrets with masked placeholders
    if ch_type == "discord":
        new_val = new_cfg.get("webhook_url", "").strip()
        if not new_val or "******" in new_val:
            new_cfg["webhook_url"] = existing_cfg.get("webhook_url", "")
        if payload.enabled and new_cfg.get("webhook_url"):
            try:
                validate_discord_webhook_url(new_cfg["webhook_url"])
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "INVALID_WEBHOOK_URL", "message": str(e)}},
                )

    elif ch_type == "telegram":
        new_token = new_cfg.get("bot_token", "").strip()
        if not new_token or "******" in new_token:
            new_cfg["bot_token"] = existing_cfg.get("bot_token", "")
        if payload.enabled and new_cfg.get("bot_token"):
            try:
                validate_telegram_config(new_cfg.get("bot_token", ""), new_cfg.get("chat_id", ""))
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "INVALID_TELEGRAM_CONFIG", "message": str(e)}},
                )

    elif ch_type == "email":
        new_pass = new_cfg.get("smtp_password", "").strip()
        if not new_pass or "******" in new_pass:
            new_cfg["smtp_password"] = existing_cfg.get("smtp_password", "")

    # Encrypt sensitive credentials at rest
    encrypted_cfg = encrypt_channel_config(ch_type, new_cfg)
    channel.configuration_json = encrypted_cfg
    channel.enabled = payload.enabled
    db.commit()
    db.refresh(channel)

    return NotificationChannelResponse(
        id=channel.id,
        monitor_id=channel.monitor_id,
        channel_type=ch_type,
        enabled=channel.enabled,
        configuration=sanitize_channel_config(ch_type, new_cfg),
        created_at=channel.created_at,
    )


@router.post("/settings/notifications/{channel_type}/test", response_model=TestNotificationResponse)
def test_channel_notification(
    channel_type: str,
    payload: Optional[TestNotificationRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Dispatches a test notification to verify connectivity.
    Merges existing stored secrets if caller passed masked secret fields.
    """
    ch_type = channel_type.lower()
    channel = get_or_create_global_channel(db, ch_type)
    existing_cfg = decrypt_channel_config(ch_type, channel.configuration_json or {})

    input_cfg = (payload.configuration if payload and payload.configuration else {})
    merged_cfg = dict(existing_cfg)
    for k, v in input_cfg.items():
        v_str = str(v).strip()
        if v_str and "******" not in v_str:
            merged_cfg[k] = v

    success, msg = send_test_notification(ch_type, merged_cfg)
    return TestNotificationResponse(
        success=success,
        message=sanitize_error_message(msg),
        channel_type=ch_type,
    )


@router.get("/notifications/outbox", response_model=List[NotificationOutboxItemResponse])
def list_notification_outbox(
    limit: int = Query(50, ge=1, le=200),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Returns notification delivery history with sanitized error messages and monitor metadata."""
    query = db.query(NotificationOutbox).order_by(NotificationOutbox.created_at.desc())
    if state:
        try:
            state_enum = OutboxStateEnum(state.lower())
            query = query.filter(NotificationOutbox.state == state_enum)
        except ValueError:
            pass

    items = query.limit(limit).all()

    # Preload monitors & channels for display
    monitor_ids = {item.monitor_id for item in items}
    channel_ids = {item.channel_id for item in items}

    monitors_map = {m.id: m for m in db.query(Monitor).filter(Monitor.id.in_(monitor_ids)).all()} if monitor_ids else {}
    channels_map = {c.id: c for c in db.query(NotificationChannel).filter(NotificationChannel.id.in_(channel_ids)).all()} if channel_ids else {}

    results = []
    for it in items:
        m = monitors_map.get(it.monitor_id)
        ch = channels_map.get(it.channel_id)
        ch_type = ch.channel_type.value if ch else "unknown"

        results.append(
            NotificationOutboxItemResponse(
                id=it.id,
                monitor_id=it.monitor_id,
                monitor_name=m.name if m else "Unknown Monitor",
                monitor_url=m.url if m else "",
                version_id=it.version_id,
                channel_id=it.channel_id,
                channel_type=ch_type,
                state=it.state.value if hasattr(it.state, "value") else str(it.state),
                attempts=it.attempts,
                last_error=sanitize_error_message(it.last_error),
                sent_at=it.sent_at,
                created_at=it.created_at,
            )
        )
    return results


# Per-monitor notification channel routes
@router.get("/monitors/{monitor_id}/channels", response_model=List[NotificationChannelResponse])
def get_monitor_channels(monitor_id: uuid.UUID, db: Session = Depends(get_db)):
    """Returns channels configured specifically for a single monitor."""
    channels = db.query(NotificationChannel).filter(NotificationChannel.monitor_id == monitor_id).all()
    return [
        NotificationChannelResponse(
            id=c.id,
            monitor_id=c.monitor_id,
            channel_type=c.channel_type.value,
            enabled=c.enabled,
            configuration=sanitize_channel_config(
                c.channel_type.value,
                decrypt_channel_config(c.channel_type.value, c.configuration_json or {}),
            ),
            created_at=c.created_at,
        )
        for c in channels
    ]
