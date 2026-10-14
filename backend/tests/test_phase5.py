import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from rq import SimpleWorker, Queue

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.models import (
    Monitor,
    MonitorRule,
    CheckRun,
    Version,
    NotificationChannel,
    NotificationOutbox,
    CheckRunStateEnum,
    MonitorStatusEnum,
    SensitivityEnum,
    RuleTypeEnum,
    ChannelTypeEnum,
    OutboxStateEnum,
    utc_now,
)
from app.services.security import canonicalize_url
from app.services.queue import enqueue_check, get_redis_connection
from app.services.notifier import (
    create_outbox_entries_for_changed_version,
    process_outbox_entry,
    send_test_notification,
    test_delivery_sink,
)
from app.schemas.notifications import sanitize_channel_config, mask_secret

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_mode(monkeypatch):
    monkeypatch.setattr(settings, "TEST_MODE", True)
    test_delivery_sink.clear()


# -------------------------------------------------------------------------
# 1. Confirmed Change Generates Notification Event
# -------------------------------------------------------------------------
def test_confirmed_change_generates_notification_event():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=2500"
        canon = canonicalize_url(url)
        monitor = Monitor(
            name="Notification Alert Test",
            url=url,
            canonical_url=canon,
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Configure an enabled Discord notification channel
        channel = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum.DISCORD,
            configuration_json={"webhook_url": "https://discord.com/api/webhooks/mock/test123"},
            enabled=True,
        )
        db.add(channel)
        db.commit()

        # 1. Baseline Run -> must NOT generate outbox alert
        run_base = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        assert run_base.state == CheckRunStateEnum.BASELINE

        outbox_base = db.query(NotificationOutbox).filter(NotificationOutbox.monitor_id == monitor.id).all()
        assert len(outbox_base) == 0, "Baseline capture must never generate notifications"

        # 2. Update fixture URL to trigger CHANGED
        url_changed = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=3500"
        monitor.url = url_changed
        monitor.canonical_url = canonicalize_url(url_changed)
        db.commit()

        run_changed = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        assert run_changed.state == CheckRunStateEnum.CHANGED

        # Verify notification outbox entry was created
        outbox_items = db.query(NotificationOutbox).filter(NotificationOutbox.monitor_id == monitor.id).all()
        assert len(outbox_items) == 1
        item = outbox_items[0]
        assert item.channel_id == channel.id
        assert item.version_id is not None
        assert item.attempts >= 0

        # Deliver outbox item
        process_outbox_entry(str(item.id))
        db.expire_all()
        refreshed = db.query(NotificationOutbox).filter(NotificationOutbox.id == item.id).first()
        assert refreshed.state == OutboxStateEnum.SENT
        assert refreshed.sent_at is not None

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 2. Baseline and Unchanged Checks Never Generate Alerts
# -------------------------------------------------------------------------
def test_baseline_and_unchanged_never_generate_alerts():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4100"
        monitor = Monitor(
            name="No Alert Check",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Global channel
        ch = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=None,
            channel_type=ChannelTypeEnum.TELEGRAM,
            configuration_json={"bot_token": "mock_tok", "chat_id": "12345"},
            enabled=True,
        )
        db.add(ch)
        db.commit()

        # Initial baseline capture
        run1 = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        assert run1.state == CheckRunStateEnum.BASELINE

        # Exactly identical capture -> UNCHANGED
        run2 = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        assert run2.state == CheckRunStateEnum.UNCHANGED

        # Outbox should have 0 records for this monitor
        outbox = db.query(NotificationOutbox).filter(NotificationOutbox.monitor_id == monitor.id).all()
        assert len(outbox) == 0, "No alerts should exist for baseline or unchanged checks"

        db.delete(monitor)
        db.delete(ch)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 3. Failed and Blocked Checks Never Generate Content-Change Alerts
# -------------------------------------------------------------------------
def test_failed_and_blocked_never_generate_content_alerts():
    db = SessionLocal()
    try:
        # 1. Error 500 URL
        url_500 = f"http://127.0.0.1:{settings.API_PORT}/fixture/error-500"
        mon_err = Monitor(
            name="Error 500 Monitor",
            url=url_500,
            canonical_url=canonicalize_url(url_500),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        # 2. Blocked URL
        url_blk = f"http://127.0.0.1:{settings.API_PORT}/fixture/blocked"
        mon_blk = Monitor(
            name="Blocked Monitor",
            url=url_blk,
            canonical_url=canonicalize_url(url_blk),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add_all([mon_err, mon_blk])
        db.commit()
        db.refresh(mon_err)
        db.refresh(mon_blk)

        # Global channel
        ch = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=None,
            channel_type=ChannelTypeEnum.DISCORD,
            configuration_json={"webhook_url": "mock_wh"},
            enabled=True,
        )
        db.add(ch)
        db.commit()

        run_err = enqueue_check(mon_err.id, db=db, force_async=False)
        run_blk = enqueue_check(mon_blk.id, db=db, force_async=False)
        db.expire_all()

        assert run_err.state in [CheckRunStateEnum.ERROR, CheckRunStateEnum.BLOCKED]
        assert run_blk.state in [CheckRunStateEnum.BLOCKED, CheckRunStateEnum.ERROR]

        outbox_err = db.query(NotificationOutbox).filter(NotificationOutbox.monitor_id == mon_err.id).all()
        outbox_blk = db.query(NotificationOutbox).filter(NotificationOutbox.monitor_id == mon_blk.id).all()
        assert len(outbox_err) == 0
        assert len(outbox_blk) == 0

        db.delete(mon_err)
        db.delete(mon_blk)
        db.delete(ch)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 4. Duplicate Processing Does Not Generate Duplicate Notification Records
# -------------------------------------------------------------------------
def test_duplicate_processing_idempotency():
    db = SessionLocal()
    try:
        monitor = Monitor(
            name="Idempotency Test Monitor",
            url="http://127.0.0.1:8000/fixture/product",
            canonical_url="http://127.0.0.1:8000/fixture/product",
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        version = Version(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            sequence_number=2,
            content_hash="test_hash_unique",
            normalized_text="sample text",
            screenshot_path="data/test.png",
            captured_at=utc_now(),
        )
        ch = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum.DISCORD,
            configuration_json={"webhook_url": "mock_discord"},
            enabled=True,
        )
        db.add_all([version, ch])
        db.commit()

        # Call create_outbox_entries 1st time
        entries1 = create_outbox_entries_for_changed_version(db, monitor, version, "Change 1", force_async=False)
        assert len(entries1) == 1

        # Call create_outbox_entries 2nd time for identical version and monitor
        entries2 = create_outbox_entries_for_changed_version(db, monitor, version, "Change 1 duplicate", force_async=False)
        assert len(entries2) == 0, "Second call must deduplicate and return 0 new entries"

        # Check total records in database
        total = db.query(NotificationOutbox).filter(
            NotificationOutbox.monitor_id == monitor.id,
            NotificationOutbox.version_id == version.id,
        ).count()
        assert total == 1

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 5. Discord and Telegram Payloads and Formatting
# -------------------------------------------------------------------------
def test_discord_and_telegram_payloads():
    # Test Discord formatting
    ok_discord, msg_discord = send_test_notification("discord", {"webhook_url": "https://discord.mock/hook"})
    assert ok_discord is True
    assert any(item["channel"] == "discord" for item in test_delivery_sink)

    # Test Telegram formatting
    ok_tg, msg_tg = send_test_notification("telegram", {"bot_token": "mock_bot_123", "chat_id": "999888"})
    assert ok_tg is True
    assert any(item["channel"] == "telegram" for item in test_delivery_sink)


# -------------------------------------------------------------------------
# 6. SMTP Delivery Tested Through Fake/Local Transport
# -------------------------------------------------------------------------
def test_smtp_delivery_via_mock_transport():
    smtp_cfg = {
        "smtp_host": "mock",
        "smtp_port": 587,
        "smtp_user": "test_user@example.com",
        "smtp_password": "supersecretpassword",
        "smtp_tls": True,
        "from_email": "alerts@changedetector.local",
        "to_email": "admin@example.com",
    }
    ok_smtp, msg_smtp = send_test_notification("email", smtp_cfg)
    assert ok_smtp is True
    assert any(item["channel"] == "email" and item["to"] == "admin@example.com" for item in test_delivery_sink)


# -------------------------------------------------------------------------
# 7. Notification Failures Retry Safely With Bounded Attempts
# -------------------------------------------------------------------------
def test_notification_failure_records_error_and_retries_safely():
    db = SessionLocal()
    try:
        monitor = Monitor(
            name="Retry Failure Monitor",
            url="http://127.0.0.1:8000/fixture/product",
            canonical_url="http://127.0.0.1:8000/fixture/product",
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        version = Version(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            sequence_number=1,
            content_hash="hash_fail",
            normalized_text="fail text",
            screenshot_path="data/fail.png",
            captured_at=utc_now(),
        )
        # Invalid telegram configuration that will fail
        ch = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum.TELEGRAM,
            configuration_json={"bot_token": "real_invalid_token", "chat_id": ""},
            enabled=True,
        )
        db.add_all([monitor, version, ch])
        db.commit()

        outbox = NotificationOutbox(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            version_id=version.id,
            channel_id=ch.id,
            state=OutboxStateEnum.PENDING,
            attempts=0,
        )
        db.add(outbox)
        db.commit()

        # Process entry -> should encounter error and update last_error safely
        process_outbox_entry(str(outbox.id))

        db.expire_all()
        refreshed = db.query(NotificationOutbox).filter(NotificationOutbox.id == outbox.id).first()
        assert refreshed.attempts >= 1
        assert refreshed.last_error is not None
        assert refreshed.state in [OutboxStateEnum.PENDING, OutboxStateEnum.FAILED]

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 8. Secret Values Are Never Returned in Plaintext to Frontend
# -------------------------------------------------------------------------
def test_secrets_never_returned_to_frontend():
    res = client.get("/api/settings/notifications")
    assert res.status_code == 200
    data = res.json()
    assert "discord" in data
    assert "telegram" in data
    assert "email" in data

    # Update with real-looking secrets
    update_res = client.put(
        "/api/settings/notifications/email",
        json={
            "enabled": True,
            "configuration": {
                "smtp_host": "smtp.mailgun.org",
                "smtp_port": 587,
                "smtp_user": "postmaster@mycorp.com",
                "smtp_password": "my_top_secret_smtp_password_123",
                "to_email": "team@mycorp.com",
            },
        },
    )
    assert update_res.status_code == 200
    resp_cfg = update_res.json()["configuration"]
    assert "my_top_secret_smtp_password_123" not in str(resp_cfg)
    assert "******" in resp_cfg["smtp_password"]

    # Verify subsequent GET also masks the password
    get_res = client.get("/api/settings/notifications")
    email_cfg = get_res.json()["email"]["configuration"]
    assert "my_top_secret_smtp_password_123" not in str(email_cfg)
    assert "******" in email_cfg["smtp_password"]


# -------------------------------------------------------------------------
# 9. Activity Feed Uses Real Database Records
# -------------------------------------------------------------------------
def test_activity_feed_real_records():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=9900"
        monitor = Monitor(
            name="Activity Stream Monitor",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline capture generates baseline_created event in check_runs
        run_base = enqueue_check(monitor.id, db=db, force_async=False)

        res = client.get("/api/activity?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) > 0

        # Verify event types and schema fields
        found_baseline = False
        for item in data["items"]:
            assert "id" in item
            assert "event_type" in item
            assert "status" in item
            assert "monitor_id" in item
            assert "timestamp" in item
            if item["monitor_id"] == str(monitor.id) and item["event_type"] == "baseline_created":
                found_baseline = True
        assert found_baseline is True, "Activity feed must display real baseline_created database event"

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 10. Settings Persist Correctly
# -------------------------------------------------------------------------
def test_settings_persistence_across_requests():
    # Update discord channel
    res = client.put(
        "/api/settings/notifications/discord",
        json={
            "enabled": True,
            "configuration": {
                "webhook_url": "https://discord.com/api/webhooks/999/realtokenxyz"
            },
        },
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True

    # Retrieve again
    get_res = client.get("/api/settings/notifications")
    discord_setting = get_res.json()["discord"]
    assert discord_setting["enabled"] is True
    assert "******" in discord_setting["configuration"]["webhook_url"]
    assert "realtokenxyz" not in discord_setting["configuration"]["webhook_url"]
