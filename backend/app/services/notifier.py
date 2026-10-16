import smtplib
import uuid
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional, List
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.models import (
    Monitor,
    Version,
    NotificationChannel,
    NotificationOutbox,
    OutboxStateEnum,
    ChannelTypeEnum,
    utc_now,
)
from app.services.security import (
    validate_discord_webhook_url,
    validate_telegram_config,
    sanitize_error_message,
    decrypt_channel_config,
)

logger = logging.getLogger("notifications")

# In-memory test delivery sink for automated tests verification
test_delivery_sink: List[Dict[str, Any]] = []


def build_comparison_url(monitor_id: uuid.UUID) -> str:
    """Builds frontend URL to the monitor comparison page."""
    return f"http://localhost:5173/#monitors/{monitor_id}"


def dispatch_discord(
    webhook_url: str,
    monitor_name: str,
    monitor_url: str,
    change_summary: str,
    timestamp: datetime,
    comparison_url: str,
) -> None:
    """Delivers Discord embed via webhook with SSRF and error protections."""
    validate_discord_webhook_url(webhook_url)

    if settings.TEST_MODE and ("mock" in webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/real_")):
        # Mock delivery sink for test suite
        test_delivery_sink.append({
            "channel": "discord",
            "webhook_url": webhook_url,
            "monitor_name": monitor_name,
            "summary": change_summary,
            "time": timestamp.isoformat(),
        })
        return

    payload = {
        "content": f"🚨 **Website Change Detected:** `{monitor_name}`",
        "embeds": [
            {
                "title": f"Change Detected on {monitor_name}",
                "description": change_summary or "Content modification detected.",
                "url": monitor_url,
                "color": 3447003,  # Blue accent
                "fields": [
                    {"name": "Target URL", "value": monitor_url, "inline": False},
                    {"name": "Detected At", "value": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"), "inline": True},
                    {"name": "Comparison", "value": f"[View Version Comparison]({comparison_url})", "inline": True},
                ],
                "footer": {"text": "Antigravity Website Change Detector"},
            }
        ],
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        sanitized = sanitize_error_message(str(e), secrets=[webhook_url])
        raise RuntimeError(sanitized) from None


def dispatch_telegram(
    bot_token: str,
    chat_id: str,
    monitor_name: str,
    monitor_url: str,
    change_summary: str,
    timestamp: datetime,
    comparison_url: str,
) -> None:
    """Delivers Telegram message via Bot API with validation and error protection."""
    validate_telegram_config(bot_token, chat_id)

    if settings.TEST_MODE and not bot_token.startswith("real_"):
        # Mock delivery sink for test suite
        test_delivery_sink.append({
            "channel": "telegram",
            "bot_token": bot_token,
            "chat_id": chat_id,
            "monitor_name": monitor_name,
            "summary": change_summary,
            "time": timestamp.isoformat(),
        })
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    text = (
        f"🚨 <b>Website Change Detected</b>\n\n"
        f"<b>Monitor:</b> {monitor_name}\n"
        f"<b>URL:</b> {monitor_url}\n"
        f"<b>Time:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"<b>Summary:</b> {change_summary}\n\n"
        f"<a href=\"{comparison_url}\">👉 View Version Comparison</a>"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        sanitized = sanitize_error_message(str(e), secrets=[bot_token, url])
        raise RuntimeError(sanitized) from None


def dispatch_email(
    config: Dict[str, Any],
    monitor_name: str,
    monitor_url: str,
    change_summary: str,
    timestamp: datetime,
    comparison_url: str,
) -> None:
    """Delivers Email notification using configured SMTP credentials."""
    smtp_host = config.get("smtp_host")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user")
    smtp_password = config.get("smtp_password")
    use_tls = config.get("smtp_tls", True)
    from_email = config.get("from_email") or smtp_user or "alerts@changedetector.local"
    to_email = config.get("to_email")

    if not smtp_host or not to_email:
        raise ValueError("SMTP host and to_email are required for email delivery.")

    if settings.TEST_MODE and (smtp_host == "mock" or smtp_host == "localhost"):
        # Local mock transport for test suite
        test_delivery_sink.append({
            "channel": "email",
            "to": to_email,
            "from": from_email,
            "subject": f"[Change Detector] Change detected on {monitor_name}",
            "summary": change_summary,
        })
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Change Detected] {monitor_name}"
    msg["From"] = from_email
    msg["To"] = to_email

    text_body = (
        f"Website Change Detected\n\n"
        f"Monitor: {monitor_name}\n"
        f"Target URL: {monitor_url}\n"
        f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Summary: {change_summary}\n\n"
        f"Comparison Link: {comparison_url}\n"
    )
    html_body = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
          <h2 style="color: #2563eb; margin-top: 0;">🚨 Website Change Detected</h2>
          <p><strong>Monitor:</strong> {monitor_name}</p>
          <p><strong>URL:</strong> <a href="{monitor_url}">{monitor_url}</a></p>
          <p><strong>Timestamp:</strong> {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
          <div style="background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
            <strong>Change Summary:</strong><br />
            {change_summary}
          </div>
          <div style="margin-top: 24px;">
            <a href="{comparison_url}" style="background-color: #2563eb; color: #ffffff; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: 500; display: inline-block;">
              View Version Comparison
            </a>
          </div>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    if smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)

    try:
        server.ehlo()
        if use_tls and smtp_port != 465:
            server.starttls()
            server.ehlo()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_test_notification(
    channel_type: str,
    config: Dict[str, Any],
    verification_code: Optional[str] = None,
    monitor_name: Optional[str] = None,
    monitor_url: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validates credentials and delivers a test notification for verification.
    Returns (success: bool, message: str).
    """
    ch_type = channel_type.lower()
    now = utc_now()
    if verification_code:
        summary = (
            f"Verification Code: [{verification_code}]. "
            "Enter this code in your evaluation workspace to verify destination control and activate automated alerts."
        )
    else:
        summary = "This is a test notification confirming your channel configuration works properly."
    target_name = monitor_name or ("Verification Test" if verification_code else "Test Notification")
    target_url = monitor_url or "https://example.com"
    comparison_url = "http://localhost:5173/#settings"
    decrypted_config = decrypt_channel_config(ch_type, config)

    try:
        if ch_type == "discord":
            webhook_url = decrypted_config.get("webhook_url")
            if not webhook_url:
                return False, "Discord webhook URL is required."
            dispatch_discord(
                webhook_url=webhook_url,
                monitor_name=target_name,
                monitor_url=target_url,
                change_summary=summary,
                timestamp=now,
                comparison_url=comparison_url,
            )
            return True, "Discord test notification sent successfully."

        elif ch_type == "telegram":
            bot_token = decrypted_config.get("bot_token")
            chat_id = decrypted_config.get("chat_id")
            if not bot_token or not chat_id:
                return False, "Telegram bot_token and chat_id are required."
            dispatch_telegram(
                bot_token=bot_token,
                chat_id=chat_id,
                monitor_name=target_name,
                monitor_url=target_url,
                change_summary=summary,
                timestamp=now,
                comparison_url=comparison_url,
            )
            return True, "Telegram test notification sent successfully."

        elif ch_type == "email":
            dispatch_email(
                config=decrypted_config,
                monitor_name=target_name,
                monitor_url=target_url,
                change_summary=summary,
                timestamp=now,
                comparison_url=comparison_url,
            )
            return True, "Email test notification sent successfully."

        else:
            return False, f"Unsupported channel type: {channel_type}"

    except Exception as e:
        secrets_to_strip = [
            decrypted_config.get("webhook_url"),
            decrypted_config.get("bot_token"),
            decrypted_config.get("smtp_password"),
        ]
        sanitized = sanitize_error_message(str(e), secrets=secrets_to_strip)
        logger.error(f"Test notification failure for {channel_type}: {sanitized}")
        return False, f"Delivery failed: {sanitized}"


def create_outbox_entries_for_changed_version(
    db: Session,
    monitor: Monitor,
    version: Version,
    change_summary: str,
    force_async: Optional[bool] = None,
) -> List[NotificationOutbox]:
    """
    Generates outbox records strictly for confirmed CHANGED results.
    Guarantees:
    - Never triggers on BASELINE, UNCHANGED, ERROR, BLOCKED, or rebaselines.
    - Idempotency key (monitor_id, version_id, channel_id) ensures no duplicate records.
    - Persists outbox rows and enqueues background delivery jobs.
    - For judge session monitors: enforces destination verification and bounded alert volume.
    - Completely isolates judge channels from admin global channels.
    """
    if getattr(monitor, "judge_session_id", None):
        # 1. Bounded alert volume: max 10 alerts total for this judge session
        session_alerts_count = (
            db.query(NotificationOutbox)
            .join(Monitor, NotificationOutbox.monitor_id == Monitor.id)
            .filter(Monitor.judge_session_id == monitor.judge_session_id)
            .count()
        )
        if session_alerts_count >= 10:
            logger.warning(f"Judge session {monitor.judge_session_id} reached alert volume limit (10).")
            return []

        # 2. Query only monitor-specific channels owned by this monitor that are enabled
        raw_channels = (
            db.query(NotificationChannel)
            .filter(
                NotificationChannel.monitor_id == monitor.id,
                NotificationChannel.enabled.is_(True),
            )
            .all()
        )
        # 3. Only include channels that have verified destination proof
        channels = []
        for ch in raw_channels:
            cfg = decrypt_channel_config(ch.channel_type.value, ch.configuration_json or {})
            if cfg.get("is_verified", False):
                channels.append(ch)
            else:
                logger.info(f"Skipping unverified judge channel {ch.id}")
    else:
        # Admin monitor: Query monitor-specific channels and global channels that are enabled
        channels = (
            db.query(NotificationChannel)
            .filter(
                (NotificationChannel.monitor_id == monitor.id) | (NotificationChannel.monitor_id.is_(None)),
                NotificationChannel.enabled.is_(True),
            )
            .all()
        )

    if not channels:
        logger.info(f"No active notification channels configured for monitor {monitor.id}")
        return []

    created_items: List[NotificationOutbox] = []
    comparison_url = build_comparison_url(monitor.id)

    for ch in channels:
        # Check existing outbox entry (Idempotency check)
        existing = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.monitor_id == monitor.id,
                NotificationOutbox.version_id == version.id,
                NotificationOutbox.channel_id == ch.id,
            )
            .first()
        )
        if existing:
            continue

        outbox_entry = NotificationOutbox(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            version_id=version.id,
            channel_id=ch.id,
            state=OutboxStateEnum.PENDING,
            attempts=0,
            last_error=None,
        )
        db.add(outbox_entry)
        created_items.append(outbox_entry)

    if created_items:
        db.commit()
        for item in created_items:
            db.refresh(item)
            # Enqueue background delivery
            from app.services.queue import get_queue
            try:
                q = get_queue("checks", is_async=force_async)
                q.enqueue(
                    "app.services.notifier.process_outbox_entry",
                    str(item.id),
                    change_summary=change_summary,
                    comparison_url=comparison_url,
                    job_timeout=30,
                    result_ttl=3600,
                )
            except Exception as e:
                logger.error(f"Failed to enqueue outbox delivery for {item.id}: {e}")

    return created_items


def process_outbox_entry(
    outbox_id_str: str,
    change_summary: str = "",
    comparison_url: str = "",
) -> None:
    """
    RQ Worker Task: Delivers notification outbox item with bounded retries and safe error handling.
    Explicit External Semantics:
    - Retries after uncertain delivery are explicit; at-least-once delivery is performed to external endpoints.
    - Records delivery status, attempt counts, timestamps, and error messages.
    """
    outbox_id = uuid.UUID(outbox_id_str)
    db = SessionLocal()
    try:
        outbox = (
            db.query(NotificationOutbox)
            .filter(NotificationOutbox.id == outbox_id)
            .with_for_update()
            .first()
        )
        if not outbox:
            logger.warning(f"Outbox entry {outbox_id} not found.")
            return

        # If already sent, do not resend
        if outbox.state == OutboxStateEnum.SENT:
            return

        channel = db.query(NotificationChannel).filter(NotificationChannel.id == outbox.channel_id).first()
        monitor = db.query(Monitor).filter(Monitor.id == outbox.monitor_id).first()
        version = db.query(Version).filter(Version.id == outbox.version_id).first()

        if not channel or not monitor or not version:
            outbox.state = OutboxStateEnum.FAILED
            outbox.last_error = "Associated channel, monitor, or version was deleted."
            db.commit()
            return

        if not channel.enabled:
            outbox.state = OutboxStateEnum.FAILED
            outbox.last_error = "Channel is disabled."
            db.commit()
            return

        outbox.state = OutboxStateEnum.SENDING
        outbox.attempts += 1
        db.commit()

        target_summary = change_summary or f"Version {version.sequence_number} detected content changes."
        target_cmp_url = comparison_url or build_comparison_url(monitor.id)
        ch_type = channel.channel_type.value.lower() if hasattr(channel.channel_type, "value") else str(channel.channel_type).lower()
        config = decrypt_channel_config(ch_type, channel.configuration_json or {})

        # Dispatch delivery
        if ch_type == "discord":
            webhook_url = config.get("webhook_url", "")
            dispatch_discord(
                webhook_url=webhook_url,
                monitor_name=monitor.name,
                monitor_url=monitor.url,
                change_summary=target_summary,
                timestamp=version.captured_at,
                comparison_url=target_cmp_url,
            )
        elif ch_type == "telegram":
            bot_token = config.get("bot_token", "")
            chat_id = config.get("chat_id", "")
            dispatch_telegram(
                bot_token=bot_token,
                chat_id=chat_id,
                monitor_name=monitor.name,
                monitor_url=monitor.url,
                change_summary=target_summary,
                timestamp=version.captured_at,
                comparison_url=target_cmp_url,
            )
        elif ch_type == "email":
            dispatch_email(
                config=config,
                monitor_name=monitor.name,
                monitor_url=monitor.url,
                change_summary=target_summary,
                timestamp=version.captured_at,
                comparison_url=target_cmp_url,
            )
        else:
            raise ValueError(f"Unknown channel type: {ch_type}")

        # Delivery confirmed
        outbox.state = OutboxStateEnum.SENT
        outbox.sent_at = utc_now()
        outbox.last_error = None
        db.commit()
        logger.info(f"Outbox {outbox.id} successfully delivered via {ch_type}")

    except Exception as e:
        db.rollback()
        secrets_to_strip = [
            config.get("webhook_url") if isinstance(config, dict) else None,
            config.get("bot_token") if isinstance(config, dict) else None,
            config.get("smtp_password") if isinstance(config, dict) else None,
        ]
        sanitized_error = sanitize_error_message(str(e), secrets=secrets_to_strip)
        logger.warning(f"Delivery attempt {outbox.attempts} failed for outbox {outbox_id}: {sanitized_error}")

        # Refresh outbox record
        outbox = db.query(NotificationOutbox).filter(NotificationOutbox.id == outbox_id).first()
        if outbox:
            # Bounded retries: up to 3 attempts
            if outbox.attempts < 3 and not settings.TEST_MODE:
                outbox.state = OutboxStateEnum.PENDING
                outbox.last_error = f"Attempt {outbox.attempts} failed: {sanitized_error}"
                db.commit()
                # Exponential backoff: 5s, 15s
                delay = 5 * (2 ** (outbox.attempts - 1))
                from app.services.queue import get_queue
                q = get_queue("checks")
                q.enqueue_in(
                    timedelta(seconds=delay),
                    "app.services.notifier.process_outbox_entry",
                    outbox_id_str,
                    change_summary=change_summary,
                    comparison_url=comparison_url,
                )
            else:
                outbox.state = OutboxStateEnum.FAILED
                outbox.last_error = f"Max retries reached ({outbox.attempts} attempts). Last error: {sanitized_error}"
                db.commit()
    finally:
        db.close()
