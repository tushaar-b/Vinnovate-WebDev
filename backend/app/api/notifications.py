import uuid
import secrets
from datetime import timedelta, datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
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
    JudgeNotificationChannelPayload,
    JudgeTestNotificationRequest,
    JudgeTestNotificationResponse,
    JudgeVerifyChannelRequest,
    JudgeNotificationChannelResponse,
    JudgeNotificationSettingsResponse,
)
from app.services.notifier import send_test_notification
from app.services.auth import require_auth, require_admin_auth, AuthContext
from app.api.monitors import get_monitor_or_404
from app.services.judge import check_judge_test_rate_limit
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
def get_notification_settings(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_admin_auth),
):
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
    auth: AuthContext = Depends(require_admin_auth),
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
    auth: AuthContext = Depends(require_admin_auth),
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
    auth: AuthContext = Depends(require_auth),
):
    """Returns notification delivery history with sanitized error messages and monitor metadata."""
    query = db.query(NotificationOutbox).join(Monitor, NotificationOutbox.monitor_id == Monitor.id).order_by(NotificationOutbox.created_at.desc())
    if auth.is_judge:
        query = query.filter(Monitor.judge_session_id == auth.judge_session_id)
    else:
        query = query.filter(Monitor.judge_session_id.is_(None))

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
def get_monitor_channels(
    monitor_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """Returns channels configured specifically for a single monitor."""
    # Enforce monitor ownership: returns 404 if monitor doesn't belong to caller
    monitor = get_monitor_or_404(monitor_id, db, auth)
    channels = db.query(NotificationChannel).filter(NotificationChannel.monitor_id == monitor.id).all()
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


# =========================================================================
# Judge Workspace Scoped Notification Endpoints
# =========================================================================

@router.get("/judge/notifications", response_model=JudgeNotificationSettingsResponse)
def get_judge_notification_settings(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Returns notification channels associated with monitors in the anonymous judge session.
    Secrets are decrypted and securely masked before return.
    """
    if not auth.is_judge or not auth.judge_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Endpoint restricted to evaluation sessions."}},
        )

    monitors = db.query(Monitor).filter(Monitor.judge_session_id == auth.judge_session_id).all()
    monitors_map = {m.id: m for m in monitors}
    monitor_ids = list(monitors_map.keys())

    channels = (
        db.query(NotificationChannel)
        .filter(NotificationChannel.monitor_id.in_(monitor_ids))
        .all()
        if monitor_ids else []
    )

    channels_by_type: Dict[str, Optional[JudgeNotificationChannelResponse]] = {
        "discord": None,
        "telegram": None,
    }

    for ch in channels:
        ch_type = ch.channel_type.value.lower()
        if ch_type in channels_by_type:
            decrypted = decrypt_channel_config(ch_type, ch.configuration_json or {})
            is_verified = bool(decrypted.get("is_verified", False))
            sanitized = sanitize_channel_config(ch_type, decrypted)
            # Remove internal verification state from sanitized config
            sanitized.pop("_verification_code", None)
            sanitized.pop("_verification_exp", None)
            m = monitors_map.get(ch.monitor_id)

            channels_by_type[ch_type] = JudgeNotificationChannelResponse(
                id=ch.id,
                monitor_id=ch.monitor_id,
                monitor_name=m.name if m else "Unknown Monitor",
                channel_type=ch_type,
                enabled=ch.enabled,
                is_verified=is_verified,
                configuration=sanitized,
                created_at=ch.created_at,
            )

    return JudgeNotificationSettingsResponse(
        channels=channels_by_type,
        limits={
            "max_channels_per_type": 1,
            "test_rate_limit_per_hour": 3,
            "max_alerts_volume": 10,
        },
    )


@router.put("/judge/notifications/{channel_type}", response_model=JudgeNotificationChannelResponse)
def update_judge_notification_channel(
    channel_type: str,
    payload: JudgeNotificationChannelPayload,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Creates or updates a notification channel for a monitor owned by the judge session.
    Strict limits: At most 1 channel of each type per judge session.
    Enforces proof-of-control: Cannot be enabled unless destination is verified.
    """
    if not auth.is_judge or not auth.judge_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Endpoint restricted to evaluation sessions."}},
        )

    ch_type = channel_type.lower()
    if ch_type not in ["discord", "telegram"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CHANNEL", "message": f"Unsupported judge channel {channel_type}"}},
        )

    # Enforce monitor ownership
    monitor = (
        db.query(Monitor)
        .filter(
            Monitor.id == payload.monitor_id,
            Monitor.judge_session_id == auth.judge_session_id,
        )
        .first()
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found or not owned by your evaluation session."}},
        )

    # Enforce limit: At most 1 channel of each type per judge session
    judge_mon_ids = [m.id for m in db.query(Monitor.id).filter(Monitor.judge_session_id == auth.judge_session_id).all()]
    existing_ch = (
        db.query(NotificationChannel)
        .filter(
            NotificationChannel.monitor_id.in_(judge_mon_ids),
            NotificationChannel.channel_type == ChannelTypeEnum(ch_type),
        )
        .first()
        if judge_mon_ids else None
    )

    existing_cfg = decrypt_channel_config(ch_type, existing_ch.configuration_json or {}) if existing_ch else {}
    new_cfg = dict(payload.configuration or {})

    # Validate destination format & preserve masked credentials
    if ch_type == "discord":
        url = new_cfg.get("webhook_url", "").strip()
        if not url or "******" in url:
            new_cfg["webhook_url"] = existing_cfg.get("webhook_url", "")
        if not new_cfg.get("webhook_url"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DESTINATION", "message": "Discord webhook URL is required."}},
            )
        try:
            validate_discord_webhook_url(new_cfg["webhook_url"])
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_WEBHOOK_URL", "message": str(e)}},
            )
        dest_changed = (new_cfg.get("webhook_url") != existing_cfg.get("webhook_url"))

    elif ch_type == "telegram":
        token = new_cfg.get("bot_token", "").strip()
        if not token or "******" in token:
            new_cfg["bot_token"] = existing_cfg.get("bot_token", "")
        chat = str(new_cfg.get("chat_id", "")).strip()
        if not chat or "******" in chat:
            new_cfg["chat_id"] = existing_cfg.get("chat_id", "")
        if not new_cfg.get("bot_token") or not new_cfg.get("chat_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DESTINATION", "message": "Telegram bot_token and chat_id are required."}},
            )
        try:
            validate_telegram_config(new_cfg["bot_token"], str(new_cfg["chat_id"]))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_TELEGRAM_CONFIG", "message": str(e)}},
            )
        dest_changed = (
            new_cfg.get("bot_token") != existing_cfg.get("bot_token")
            or str(new_cfg.get("chat_id")) != str(existing_cfg.get("chat_id"))
        )

    # If destination changed, reset verification state
    if dest_changed:
        new_cfg["is_verified"] = False
    else:
        new_cfg["is_verified"] = existing_cfg.get("is_verified", False)

    # Require proof of control before enabling
    if payload.enabled and not new_cfg.get("is_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "DESTINATION_UNVERIFIED",
                    "message": "Destination must be verified via test notification before enabling alerts. Please send a test ping.",
                }
            },
        )

    if existing_ch:
        channel = existing_ch
        channel.monitor_id = monitor.id
    else:
        channel = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum(ch_type),
            enabled=False,
            created_at=utc_now(),
        )
        db.add(channel)

    channel.enabled = payload.enabled and new_cfg.get("is_verified", False)
    channel.configuration_json = encrypt_channel_config(ch_type, new_cfg)
    db.commit()
    db.refresh(channel)

    sanitized = sanitize_channel_config(ch_type, new_cfg)
    sanitized.pop("_verification_code", None)
    sanitized.pop("_verification_exp", None)

    return JudgeNotificationChannelResponse(
        id=channel.id,
        monitor_id=channel.monitor_id,
        monitor_name=monitor.name,
        channel_type=ch_type,
        enabled=channel.enabled,
        is_verified=new_cfg.get("is_verified", False),
        configuration=sanitized,
        created_at=channel.created_at,
    )


@router.post("/judge/notifications/{channel_type}/test", response_model=JudgeTestNotificationResponse)
def test_judge_notification_channel(
    channel_type: str,
    payload: JudgeTestNotificationRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Sends a test notification to verify connectivity and issues a verification code for destination proof.
    Enforces hourly rate limit (max 3 tests per hour per judge session).
    """
    if not auth.is_judge or not auth.judge_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Endpoint restricted to evaluation sessions."}},
        )

    ch_type = channel_type.lower()
    if ch_type not in ["discord", "telegram"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CHANNEL", "message": f"Unsupported judge channel {channel_type}"}},
        )

    # Enforce monitor ownership
    monitor = (
        db.query(Monitor)
        .filter(
            Monitor.id == payload.monitor_id,
            Monitor.judge_session_id == auth.judge_session_id,
        )
        .first()
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found or not owned by your evaluation session."}},
        )

    # Enforce rate limit (max 3 tests per hour)
    check_judge_test_rate_limit(auth.judge_session_id, max_tests_per_hour=3)

    # Find existing channel or merge payload configuration
    judge_mon_ids = [m.id for m in db.query(Monitor.id).filter(Monitor.judge_session_id == auth.judge_session_id).all()]
    existing_ch = (
        db.query(NotificationChannel)
        .filter(
            NotificationChannel.monitor_id.in_(judge_mon_ids),
            NotificationChannel.channel_type == ChannelTypeEnum(ch_type),
        )
        .first()
        if judge_mon_ids else None
    )

    existing_cfg = decrypt_channel_config(ch_type, existing_ch.configuration_json or {}) if existing_ch else {}
    new_cfg = dict(existing_cfg)
    if payload.configuration:
        for k, v in payload.configuration.items():
            v_str = str(v).strip()
            if v_str and "******" not in v_str:
                new_cfg[k] = v

    # Validate destination format
    if ch_type == "discord":
        url = new_cfg.get("webhook_url", "").strip()
        if not url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DESTINATION", "message": "Discord webhook URL is required."}},
            )
        try:
            validate_discord_webhook_url(url)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_WEBHOOK_URL", "message": str(e)}},
            )
    elif ch_type == "telegram":
        token = new_cfg.get("bot_token", "").strip()
        chat = str(new_cfg.get("chat_id", "")).strip()
        if not token or not chat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DESTINATION", "message": "Telegram bot_token and chat_id are required."}},
            )
        try:
            validate_telegram_config(token, chat)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_TELEGRAM_CONFIG", "message": str(e)}},
            )

    # Generate 6-character cryptographic verification code with 15-minute TTL
    verification_code = secrets.token_hex(3).upper()
    new_cfg["_verification_code"] = verification_code
    new_cfg["_verification_exp"] = (utc_now() + timedelta(minutes=15)).isoformat()

    # Dispatch test notification with verification code
    success, msg = send_test_notification(
        channel_type=ch_type,
        config=new_cfg,
        verification_code=verification_code,
        monitor_name=monitor.name,
        monitor_url=monitor.url,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "DELIVERY_FAILED", "message": sanitize_error_message(msg)}},
        )

    # Save pending verification state in database
    if existing_ch:
        channel = existing_ch
        channel.monitor_id = monitor.id
    else:
        channel = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum(ch_type),
            enabled=False,
            created_at=utc_now(),
        )
        db.add(channel)

    channel.configuration_json = encrypt_channel_config(ch_type, new_cfg)
    db.commit()

    return JudgeTestNotificationResponse(
        success=True,
        message="Test notification sent! Check your Discord or Telegram destination for your 6-character verification code.",
        channel_type=ch_type,
        verification_required=True,
        verification_code=verification_code if getattr(settings, "TEST_MODE", False) else None,
    )


@router.post("/judge/notifications/{channel_type}/verify", response_model=JudgeTestNotificationResponse)
def verify_judge_notification_channel(
    channel_type: str,
    payload: JudgeVerifyChannelRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Verifies that the judge controls the destination by validating the 6-character verification code.
    Upon successful verification, activates and enables alerts for the channel.
    """
    if not auth.is_judge or not auth.judge_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Endpoint restricted to evaluation sessions."}},
        )

    ch_type = channel_type.lower()
    if ch_type not in ["discord", "telegram"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CHANNEL", "message": f"Unsupported judge channel {channel_type}"}},
        )

    # Enforce monitor ownership
    monitor = (
        db.query(Monitor)
        .filter(
            Monitor.id == payload.monitor_id,
            Monitor.judge_session_id == auth.judge_session_id,
        )
        .first()
    )
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found or not owned by your evaluation session."}},
        )

    judge_mon_ids = [m.id for m in db.query(Monitor.id).filter(Monitor.judge_session_id == auth.judge_session_id).all()]
    channel = (
        db.query(NotificationChannel)
        .filter(
            NotificationChannel.monitor_id.in_(judge_mon_ids),
            NotificationChannel.channel_type == ChannelTypeEnum(ch_type),
        )
        .first()
        if judge_mon_ids else None
    )

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CHANNEL_NOT_FOUND", "message": "Channel not configured yet. Please send a test notification first."}},
        )

    cfg = decrypt_channel_config(ch_type, channel.configuration_json or {})
    stored_code = cfg.get("_verification_code")
    exp_str = cfg.get("_verification_exp")

    if not stored_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_VERIFICATION_PENDING", "message": "No verification pending. Please send a test notification first."}},
        )

    if exp_str:
        try:
            exp_dt = datetime.fromisoformat(exp_str)
            if utc_now() > exp_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "CODE_EXPIRED", "message": "Verification code has expired. Please send a new test notification."}},
                )
        except (ValueError, TypeError):
            pass

    if payload.code.strip().upper() != stored_code.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CODE", "message": "Invalid verification code. Please check the code sent to your Discord or Telegram destination."}},
        )

    # Verification successful
    cfg["is_verified"] = True
    cfg.pop("_verification_code", None)
    cfg.pop("_verification_exp", None)

    channel.configuration_json = encrypt_channel_config(ch_type, cfg)
    channel.enabled = True
    channel.monitor_id = monitor.id
    db.commit()
    db.refresh(channel)

    return JudgeTestNotificationResponse(
        success=True,
        message="Destination verified successfully! Automated change alerts are now active for this channel.",
        channel_type=ch_type,
        verification_required=False,
    )


@router.delete("/judge/notifications/{channel_type}")
def delete_judge_notification_channel(
    channel_type: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """Deletes a notification channel configured in the judge evaluation session."""
    if not auth.is_judge or not auth.judge_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Endpoint restricted to evaluation sessions."}},
        )

    ch_type = channel_type.lower()
    judge_mon_ids = [m.id for m in db.query(Monitor.id).filter(Monitor.judge_session_id == auth.judge_session_id).all()]
    channel = (
        db.query(NotificationChannel)
        .filter(
            NotificationChannel.monitor_id.in_(judge_mon_ids),
            NotificationChannel.channel_type == ChannelTypeEnum(ch_type),
        )
        .first()
        if judge_mon_ids else None
    )

    if channel:
        db.delete(channel)
        db.commit()

    return {"success": True, "message": f"{channel_type.capitalize()} channel removed."}

