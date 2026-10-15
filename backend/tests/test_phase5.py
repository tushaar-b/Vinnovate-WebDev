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

        # Verify notification outbox entry was created for this channel
        outbox_items = db.query(NotificationOutbox).filter(
            NotificationOutbox.monitor_id == monitor.id,
            NotificationOutbox.channel_id == channel.id,
        ).all()
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
        assert len(entries1) >= 1

        # Call create_outbox_entries 2nd time for identical version and monitor
        entries2 = create_outbox_entries_for_changed_version(db, monitor, version, "Change 1 duplicate", force_async=False)
        assert len(entries2) == 0, "Second call must deduplicate and return 0 new entries"

        # Check total records for this specific channel
        total = db.query(NotificationOutbox).filter(
            NotificationOutbox.monitor_id == monitor.id,
            NotificationOutbox.version_id == version.id,
            NotificationOutbox.channel_id == ch.id,
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
        m_id = uuid.uuid4()
        monitor = Monitor(
            id=m_id,
            name="Retry Failure Monitor",
            url="http://127.0.0.1:8000/fixture/product",
            canonical_url="http://127.0.0.1:8000/fixture/product",
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        version = Version(
            id=uuid.uuid4(),
            monitor_id=m_id,
            sequence_number=1,
            content_hash="hash_fail",
            normalized_text="fail text",
            screenshot_path="data/fail.png",
            captured_at=utc_now(),
        )
        # Invalid telegram configuration that will fail
        ch = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=m_id,
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

        res = client.get(f"/api/activity?monitor_id={monitor.id}")
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


# -------------------------------------------------------------------------
# 11. Discord Webhook SSRF Rejection
# -------------------------------------------------------------------------
def test_discord_webhook_ssrf_rejection():
    # 1. Reject private IP / non-HTTPS
    res_private = client.put(
        "/api/settings/notifications/discord",
        json={
            "enabled": True,
            "configuration": {"webhook_url": "http://127.0.0.1:8000/internal-api"},
        },
    )
    assert res_private.status_code == 400
    assert "INVALID_WEBHOOK_URL" in res_private.text

    # 2. Reject arbitrary non-Discord destination domain
    res_external = client.put(
        "/api/settings/notifications/discord",
        json={
            "enabled": True,
            "configuration": {"webhook_url": "https://evil-attacker.example.com/log"},
        },
    )
    assert res_external.status_code == 400
    assert "INVALID_WEBHOOK_URL" in res_external.text

    # 3. Accept valid discord.com HTTPS destination
    res_valid = client.put(
        "/api/settings/notifications/discord",
        json={
            "enabled": True,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/valid/test1234"},
        },
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["enabled"] is True


# -------------------------------------------------------------------------
# 12. Notification Error Secret Leakage Regression Test (TASK 1)
# -------------------------------------------------------------------------
def test_error_message_sanitization_discord_and_telegram_secrets():
    from app.services.security import sanitize_error_message

    fake_secret = "TopSecretWebhookToken9876543210XYZ"
    discord_url_with_secret = f"https://discord.com/api/webhooks/1234567890/{fake_secret}"

    # 1. Test raw exception string sanitization
    raw_httpx_exc = f"Client error '404 Not Found' for url '{discord_url_with_secret}'"
    sanitized = sanitize_error_message(raw_httpx_exc, secrets=[fake_secret, discord_url_with_secret])
    assert fake_secret not in sanitized
    assert "[REDACTED]" in sanitized
    assert "https://discord.com/api/webhooks/1234567890/[REDACTED]" in sanitized

    # 2. Test Telegram bot token sanitization
    fake_tg_token = "123456789:ABCdefGhI_jkLmNoPqRsTuVwXyZ123456789"
    raw_tg_exc = f"Client error '401 Unauthorized' for url 'https://api.telegram.org/bot{fake_tg_token}/sendMessage'"
    sanitized_tg = sanitize_error_message(raw_tg_exc, secrets=[fake_tg_token])
    assert fake_tg_token not in sanitized_tg
    assert "https://api.telegram.org/bot[REDACTED]/sendMessage" in sanitized_tg

    # 3. Test embedded credentials sanitization
    raw_auth_exc = "Failed to connect to https://app_user:SuperSecretPassword123@smtp.mailprovider.com:587"
    sanitized_auth = sanitize_error_message(raw_auth_exc)
    assert "SuperSecretPassword123" not in sanitized_auth
    assert "app_user:[REDACTED]@smtp.mailprovider.com:587" in sanitized_auth

    # 4. Verify historical stored error sanitization via API endpoints
    db = SessionLocal()
    try:
        m_id = uuid.uuid4()
        mon = Monitor(
            id=m_id,
            name="Sanitization API Test",
            url="http://127.0.0.1:8000/fixture/product",
            canonical_url="http://127.0.0.1:8000/fixture/product",
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(mon)

        v_id = uuid.uuid4()
        ver = Version(
            id=v_id,
            monitor_id=m_id,
            sequence_number=1,
            content_hash="hash_san",
            normalized_text="san text",
            screenshot_path="data/screenshots/test.png",
        )
        db.add(ver)

        ch_id = uuid.uuid4()
        ch = NotificationChannel(
            id=ch_id,
            monitor_id=m_id,
            channel_type=ChannelTypeEnum.DISCORD,
            configuration_json={"webhook_url": discord_url_with_secret},
            enabled=True,
        )
        db.add(ch)

        # Deliberately store an error that contains the secret token (simulating historical unsanitized row)
        outbox_id = uuid.uuid4()
        historical_raw_error = f"Max retries reached. Last error: Client error '400 Bad Request' for url '{discord_url_with_secret}'"
        outbox_entry = NotificationOutbox(
            id=outbox_id,
            monitor_id=m_id,
            version_id=v_id,
            channel_id=ch_id,
            state=OutboxStateEnum.FAILED,
            attempts=3,
            last_error=historical_raw_error,
        )
        db.add(outbox_entry)
        db.commit()

        # Query Outbox API: verify fake_secret is completely absent from API JSON response
        outbox_res = client.get("/api/notifications/outbox")
        assert outbox_res.status_code == 200
        outbox_data = outbox_res.json()
        matching_outbox = next((item for item in outbox_data if item["id"] == str(outbox_id)), None)
        assert matching_outbox is not None
        assert fake_secret not in matching_outbox["last_error"]
        assert "[REDACTED]" in matching_outbox["last_error"]

        # Query Activity API: verify fake_secret is completely absent from Activity JSON response
        activity_res = client.get(f"/api/activity?monitor_id={m_id}")
        assert activity_res.status_code == 200
        act_data = activity_res.json()
        act_item = next((item for item in act_data["items"] if item["id"] == f"outbox-{outbox_id}"), None)
        assert act_item is not None
        assert fake_secret not in act_item["summary"]
        assert fake_secret not in str(act_item.get("metadata", {}))
        assert "[REDACTED]" in act_item["summary"]

        db.delete(mon)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 13. Actual Credential Storage Security at Rest (TASK 2)
# -------------------------------------------------------------------------
def test_credentials_encrypted_at_rest_in_postgres():
    db = SessionLocal()
    try:
        secret_webhook = "https://discord.com/api/webhooks/987654321/SecretTokenAtRest999"

        # 1. Update settings via PUT endpoint
        put_res = client.put(
            "/api/settings/notifications/discord",
            json={
                "enabled": True,
                "configuration": {"webhook_url": secret_webhook},
            },
        )
        assert put_res.status_code == 200

        # 2. Inspect database row directly in PostgreSQL: verify it is NOT stored as plaintext
        db.expire_all()
        ch = db.query(NotificationChannel).filter(
            NotificationChannel.monitor_id.is_(None),
            NotificationChannel.channel_type == ChannelTypeEnum.DISCORD,
        ).first()
        assert ch is not None
        stored_cfg = ch.configuration_json
        assert "webhook_url" in stored_cfg

        # Must be encrypted using authenticated encryption prefix
        assert stored_cfg["webhook_url"].startswith("enc:v1:")
        assert "SecretTokenAtRest999" not in stored_cfg["webhook_url"]
        assert "987654321" not in stored_cfg["webhook_url"]

        # 3. GET /api/settings/notifications: verify secret is masked
        get_res = client.get("/api/settings/notifications")
        assert get_res.status_code == 200
        discord_cfg = get_res.json()["discord"]["configuration"]
        assert "SecretTokenAtRest999" not in discord_cfg["webhook_url"]
        assert "******" in discord_cfg["webhook_url"]

        # 4. Verify updating with masked placeholder preserves the existing encrypted secret
        put_masked = client.put(
            "/api/settings/notifications/discord",
            json={
                "enabled": True,
                "configuration": {"webhook_url": discord_cfg["webhook_url"]},
            },
        )
        assert put_masked.status_code == 200

        db.expire_all()
        ch_after = db.query(NotificationChannel).filter(
            NotificationChannel.monitor_id.is_(None),
            NotificationChannel.channel_type == ChannelTypeEnum.DISCORD,
        ).first()
        from app.services.security import decrypt_channel_config
        decrypted = decrypt_channel_config("discord", ch_after.configuration_json)
        assert decrypted["webhook_url"] == secret_webhook

    finally:
        db.close()


def test_encryption_plaintext_compatibility_and_functions():
    from app.services.security import (
        encrypt_credential,
        decrypt_credential,
        encrypt_channel_config,
        decrypt_channel_config,
    )

    # 1. Encrypt and decrypt round trip
    raw_secret = "smtp_super_secret_pw_123"
    enc = encrypt_credential(raw_secret)
    assert enc.startswith("enc:v1:")
    assert raw_secret not in enc
    dec = decrypt_credential(enc)
    assert dec == raw_secret

    # 2. Backwards compatibility: plaintext legacy value is preserved safely
    legacy_plaintext = "https://discord.com/api/webhooks/mock/legacy"
    assert decrypt_credential(legacy_plaintext) == legacy_plaintext

    # 3. Channel config encrypt / decrypt
    config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_password": "super_secret_password",
    }
    enc_config = encrypt_channel_config("email", config)
    assert enc_config["smtp_password"].startswith("enc:v1:")
    assert enc_config["smtp_host"] == "smtp.example.com"

    dec_config = decrypt_channel_config("email", enc_config)
    assert dec_config["smtp_password"] == "super_secret_password"
    assert dec_config["smtp_host"] == "smtp.example.com"


# -------------------------------------------------------------------------
# 14. Destination Safety & SSRF Rejection (TASK 3)
# -------------------------------------------------------------------------
def test_discord_and_telegram_destination_safety():
    from app.services.security import (
        validate_discord_webhook_url,
        validate_telegram_config,
    )

    # 1. Deceptive subdomain / suffix rejection
    bad_urls = [
        "https://discord.com.attacker.com/api/webhooks/123/token",
        "https://evil-discord.com/api/webhooks/123/token",
        "https://user:pass@discord.com/api/webhooks/123/token",
        "https://discord.com:8443/api/webhooks/123/token",
        "https://discord.com/login",
        "https://discord.com/api/v10/users/@me",
        "http://discord.com/api/webhooks/123/token",
        "ftp://discord.com/api/webhooks/123/token",
    ]
    for bad_url in bad_urls:
        with pytest.raises(ValueError):
            validate_discord_webhook_url(bad_url)

    # 2. Telegram parameter injection / path traversal rejection
    bad_telegram_tokens = [
        "../../etc/passwd",
        "token/with/slashes",
        "token with spaces",
        "token\nwith\nnewlines",
        "token?query=param",
        "token#fragment",
    ]
    for bad_tok in bad_telegram_tokens:
        with pytest.raises(ValueError):
            validate_telegram_config(bad_tok, "12345678")

    # 3. Bad chat IDs
    bad_chat_ids = [
        "chat/with/slashes",
        "chat with space",
        "../../id",
    ]
    for bad_id in bad_chat_ids:
        with pytest.raises(ValueError):
            validate_telegram_config("123456789:ABCdefGhI_validtoken123", bad_id)

    # 4. Valid official endpoints pass
    validate_discord_webhook_url("https://discord.com/api/webhooks/1234567890/tokenABCdef123")
    validate_telegram_config("123456789:ABCdefGhI_validtoken123", "-100123456789")
    validate_telegram_config("123456789:ABCdefGhI_validtoken123", "@my_telegram_channel")


# -------------------------------------------------------------------------
# 15. Encryption Key Stability and Startup Abort (FINAL SIGN-OFF)
# -------------------------------------------------------------------------
def test_encryption_key_stability_and_startup_abort_on_invalid_key():
    from app.services.security import (
        encrypt_credential,
        decrypt_credential,
        reset_fernet_cache,
        validate_encryption_key_at_startup,
    )
    from app.config import settings

    original_key = settings.ENCRYPTION_KEY
    assert original_key is not None, "ENCRYPTION_KEY must be configured for test suite"

    try:
        # 1. Existing credentials remain decryptable after application restart (simulated via reset_fernet_cache)
        test_secret = "test_webhook_stability_secret_12345"
        encrypted = encrypt_credential(test_secret)
        assert encrypted.startswith("enc:v1:")

        reset_fernet_cache()
        decrypted = decrypt_credential(encrypted)
        assert decrypted == test_secret

        # 2. Startup validation passes with the correct key
        validate_encryption_key_at_startup()

        # 3. Startup fails safely with clear configuration error when key is missing and encrypted data exists
        settings.ENCRYPTION_KEY = None
        reset_fernet_cache()

        with pytest.raises(RuntimeError) as exc_missing:
            validate_encryption_key_at_startup()
        assert "CRITICAL CONFIGURATION ERROR" in str(exc_missing.value)
        assert "ENCRYPTION_KEY is not configured" in str(exc_missing.value)

        # 4. Startup fails safely when key is mismatched/invalid and encrypted data exists
        from cryptography.fernet import Fernet
        mismatched_key = Fernet.generate_key().decode()
        settings.ENCRYPTION_KEY = mismatched_key
        reset_fernet_cache()

        with pytest.raises(RuntimeError) as exc_mismatch:
            validate_encryption_key_at_startup()
        assert "CRITICAL CONFIGURATION ERROR" in str(exc_mismatch.value)
        assert "cannot decrypt existing encrypted credentials" in str(exc_mismatch.value)

    finally:
        # Restore original valid key
        settings.ENCRYPTION_KEY = original_key
        reset_fernet_cache()
        validate_encryption_key_at_startup()


# -------------------------------------------------------------------------
# 16. Discord Credential Masking & Replacement (FINAL SIGN-OFF)
# -------------------------------------------------------------------------
def test_discord_credential_masking_and_placeholder_preservation():
    from app.schemas.notifications import mask_secret

    # 1. Test mask_secret unit behavior across all official Discord domains and shapes
    raw_secret = "UltraSecretDiscordTokenABC123XYZ"
    cases = [
        f"https://discord.com/api/webhooks/1234567890/{raw_secret}",
        f"https://discordapp.com/api/webhooks/1234567890/{raw_secret}/",
        f"https://canary.discord.com/api/webhooks/1234567890/{raw_secret}?wait=true",
        f"https://ptb.discord.com/api/webhooks/1234567890/{raw_secret}#fragment",
    ]
    for c in cases:
        masked = mask_secret(c)
        assert raw_secret not in masked, f"Raw secret leaked in {masked}"
        assert masked.startswith("https://")
        assert masked.endswith("/******")
        assert "1234567890" in masked

    # 2. End-to-end API test: Set Discord webhook
    secret_token_1 = "TokenInitialVersion998877"
    url_1 = f"https://discord.com/api/webhooks/1122334455/{secret_token_1}"

    put_res1 = client.put(
        "/api/settings/notifications/discord",
        json={"enabled": True, "configuration": {"webhook_url": url_1}},
    )
    assert put_res1.status_code == 200
    res_data1 = put_res1.json()
    assert secret_token_1 not in res_data1["configuration"]["webhook_url"]
    assert res_data1["configuration"]["webhook_url"] == "https://discord.com/api/webhooks/1122334455/******"

    # 3. GET /api/settings/notifications: never returns complete stored URL
    get_res = client.get("/api/settings/notifications")
    assert get_res.status_code == 200
    discord_view = get_res.json()["discord"]["configuration"]
    assert secret_token_1 not in discord_view["webhook_url"]
    assert discord_view["webhook_url"] == "https://discord.com/api/webhooks/1122334455/******"

    # 4. Save with masked placeholder: preserves original credential
    put_masked = client.put(
        "/api/settings/notifications/discord",
        json={"enabled": True, "configuration": {"webhook_url": discord_view["webhook_url"]}},
    )
    assert put_masked.status_code == 200

    db = SessionLocal()
    try:
        db.expire_all()
        ch = db.query(NotificationChannel).filter(
            NotificationChannel.monitor_id.is_(None),
            NotificationChannel.channel_type == ChannelTypeEnum.DISCORD,
        ).first()
        from app.services.security import decrypt_channel_config
        decrypted = decrypt_channel_config("discord", ch.configuration_json)
        assert decrypted["webhook_url"] == url_1
    finally:
        db.close()

    # 5. Replace with a brand new valid URL: successfully updates
    secret_token_2 = "TokenReplacedVersion445566"
    url_2 = f"https://discord.com/api/webhooks/9988776655/{secret_token_2}"

    put_res2 = client.put(
        "/api/settings/notifications/discord",
        json={"enabled": True, "configuration": {"webhook_url": url_2}},
    )
    assert put_res2.status_code == 200
    assert secret_token_2 not in put_res2.json()["configuration"]["webhook_url"]
    assert put_res2.json()["configuration"]["webhook_url"] == "https://discord.com/api/webhooks/9988776655/******"

    db = SessionLocal()
    try:
        db.expire_all()
        ch2 = db.query(NotificationChannel).filter(
            NotificationChannel.monitor_id.is_(None),
            NotificationChannel.channel_type == ChannelTypeEnum.DISCORD,
        ).first()
        decrypted2 = decrypt_channel_config("discord", ch2.configuration_json)
        assert decrypted2["webhook_url"] == url_2
    finally:
        db.close()


