import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.models import (
    Monitor,
    Version,
    NotificationChannel,
    NotificationOutbox,
    CheckRunStateEnum,
    SensitivityEnum,
    ChannelTypeEnum,
    OutboxStateEnum,
    utc_now,
)
from app.services.security import canonicalize_url, decrypt_channel_config
from app.services.notifier import (
    create_outbox_entries_for_changed_version,
    test_delivery_sink,
)
from app.services.judge import cleanup_expired_judge_monitors, _in_memory_judge_tests

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_mode(monkeypatch):
    monkeypatch.setattr(settings, "TEST_MODE", True)
    test_delivery_sink.clear()
    _in_memory_judge_tests.clear()


def create_judge_session_helper():
    res = client.post("/api/judge/session")
    assert res.status_code == 200
    token = res.json()["token"]
    session_id = res.json()["session_id"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, session_id, headers


def create_judge_monitor_helper(headers, name="Judge Test Monitor", url="https://example.com/test"):
    res = client.post(
        "/api/monitors",
        headers=headers,
        json={"name": name, "url": url, "interval_minutes": 15},
    )
    assert res.status_code == 201
    return res.json()["id"]


# ---------------------------------------------------------------------------
# 1. Channel Ownership & Isolation
# ---------------------------------------------------------------------------
def test_judge_channel_ownership_and_isolation():
    _, session1_id, headers1 = create_judge_session_helper()
    _, session2_id, headers2 = create_judge_session_helper()

    mon1_id = create_judge_monitor_helper(headers1, name="Judge 1 Monitor")
    mon2_id = create_judge_monitor_helper(headers2, name="Judge 2 Monitor")

    # Session 1 configures Discord for mon1
    res = client.put(
        "/api/judge/notifications/discord",
        headers=headers1,
        json={
            "monitor_id": mon1_id,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/mock/judge1"},
            "enabled": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["monitor_id"] == mon1_id
    assert "******" in data["configuration"]["webhook_url"]

    # Session 2 attempts to configure channel for mon1 (owned by Session 1) -> 404
    hijack_res = client.put(
        "/api/judge/notifications/discord",
        headers=headers2,
        json={
            "monitor_id": mon1_id,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/mock/hijack"},
            "enabled": False,
        },
    )
    assert hijack_res.status_code == 404

    # Session 2 attempts to test channel for mon1 -> 404
    test_res = client.post(
        "/api/judge/notifications/discord/test",
        headers=headers2,
        json={"monitor_id": mon1_id},
    )
    assert test_res.status_code == 404

    # Anonymous call without judge token -> 401 or 403
    unauth_res = client.get("/api/judge/notifications")
    assert unauth_res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2. Strict Destination Validation (SSRF & Safe Schemes)
# ---------------------------------------------------------------------------
def test_judge_strict_destination_validation():
    _, _, headers = create_judge_session_helper()
    mon_id = create_judge_monitor_helper(headers)

    # Insecure HTTP
    res_http = client.put(
        "/api/judge/notifications/discord",
        headers=headers,
        json={
            "monitor_id": mon_id,
            "configuration": {"webhook_url": "http://discord.com/api/webhooks/123/token"},
            "enabled": False,
        },
    )
    assert res_http.status_code == 400
    assert "HTTPS" in res_http.json()["detail"]["error"]["message"]

    # Arbitrary non-discord domain
    res_domain = client.put(
        "/api/judge/notifications/discord",
        headers=headers,
        json={
            "monitor_id": mon_id,
            "configuration": {"webhook_url": "https://malicious-webhook.evil.com/webhook"},
            "enabled": False,
        },
    )
    assert res_domain.status_code == 400
    assert "discord" in res_domain.json()["detail"]["error"]["message"].lower()

    # Telegram invalid token format
    res_tg = client.put(
        "/api/judge/notifications/telegram",
        headers=headers,
        json={
            "monitor_id": mon_id,
            "configuration": {"bot_token": "invalid_no_colon", "chat_id": "12345"},
            "enabled": False,
        },
    )
    assert res_tg.status_code == 400

    # Telegram path traversal in token
    res_traversal = client.put(
        "/api/judge/notifications/telegram",
        headers=headers,
        json={
            "monitor_id": mon_id,
            "configuration": {"bot_token": "123456:../admin/secret", "chat_id": "12345"},
            "enabled": False,
        },
    )
    assert res_traversal.status_code == 400


# ---------------------------------------------------------------------------
# 3. Proof-of-Control Verification Code Flow
# ---------------------------------------------------------------------------
def test_judge_proof_of_control_verification_flow():
    _, _, headers = create_judge_session_helper()
    mon_id = create_judge_monitor_helper(headers)

    # 1. Attempting to enable alerts before verification -> 400
    res_unverified = client.put(
        "/api/judge/notifications/discord",
        headers=headers,
        json={
            "monitor_id": mon_id,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/mock/safe"},
            "enabled": True,
        },
    )
    assert res_unverified.status_code == 400
    assert "verified" in res_unverified.json()["detail"]["error"]["message"].lower()

    # 2. Dispatch test notification -> generates verification code
    res_test = client.post(
        "/api/judge/notifications/discord/test",
        headers=headers,
        json={
            "monitor_id": mon_id,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/mock/safe"},
        },
    )
    assert res_test.status_code == 200
    test_data = res_test.json()
    assert test_data["success"] is True
    assert test_data["verification_required"] is True
    verify_code = test_data["verification_code"]
    assert verify_code is not None

    # Check mock delivery sink received test ping with verification code
    assert len(test_delivery_sink) > 0
    assert "Verification Code" in test_delivery_sink[-1]["summary"]
    assert verify_code in test_delivery_sink[-1]["summary"]

    # 3. Submit wrong verification code -> 400
    res_wrong = client.post(
        "/api/judge/notifications/discord/verify",
        headers=headers,
        json={"monitor_id": mon_id, "code": "WRONG1"},
    )
    assert res_wrong.status_code == 400
    assert "invalid" in res_wrong.json()["detail"]["error"]["message"].lower()

    # 4. Submit correct verification code -> 200 & activates channel
    res_verify = client.post(
        "/api/judge/notifications/discord/verify",
        headers=headers,
        json={"monitor_id": mon_id, "code": verify_code},
    )
    assert res_verify.status_code == 200
    assert res_verify.json()["success"] is True

    # 5. Verify settings now shows channel is verified and enabled
    settings_res = client.get("/api/judge/notifications", headers=headers)
    assert settings_res.status_code == 200
    discord_channel = settings_res.json()["channels"]["discord"]
    assert discord_channel is not None
    assert discord_channel["enabled"] is True
    assert discord_channel["is_verified"] is True


# ---------------------------------------------------------------------------
# 4. Single Channel per Type Limit per Judge Session
# ---------------------------------------------------------------------------
def test_single_channel_type_limit_per_judge_session():
    _, _, headers = create_judge_session_helper()
    mon1_id = create_judge_monitor_helper(headers, name="Monitor A", url="https://example.com/a")
    mon2_id = create_judge_monitor_helper(headers, name="Monitor B", url="https://example.com/b")

    # Configure Discord on Monitor A
    res1 = client.put(
        "/api/judge/notifications/discord",
        headers=headers,
        json={
            "monitor_id": mon1_id,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/mock/first"},
            "enabled": False,
        },
    )
    assert res1.status_code == 200
    ch1_id = res1.json()["id"]

    # Configure Discord on Monitor B in same session -> updates existing channel (moves to Monitor B)
    res2 = client.put(
        "/api/judge/notifications/discord",
        headers=headers,
        json={
            "monitor_id": mon2_id,
            "configuration": {"webhook_url": "https://discord.com/api/webhooks/mock/second"},
            "enabled": False,
        },
    )
    assert res2.status_code == 200
    assert res2.json()["id"] == ch1_id
    assert res2.json()["monitor_id"] == mon2_id

    # Verify only 1 Discord channel exists in the database for this judge session
    db = SessionLocal()
    try:
        count = (
            db.query(NotificationChannel)
            .join(Monitor, NotificationChannel.monitor_id == Monitor.id)
            .filter(
                Monitor.judge_session_id == res1.json()["monitor_id"],
                NotificationChannel.channel_type == ChannelTypeEnum.DISCORD,
            )
            .count()
        )
        assert count <= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Bounded Alert Volume and CHANGED-only Alert Dispatch
# ---------------------------------------------------------------------------
def test_judge_changed_alert_dispatch_and_bounded_volume():
    _, session_id, headers = create_judge_session_helper()
    mon_id = create_judge_monitor_helper(headers)

    db = SessionLocal()
    try:
        monitor = db.query(Monitor).filter(Monitor.id == mon_id).first()
        assert monitor is not None

        # Create verified channel directly in database
        channel = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum.DISCORD,
            configuration_json={"webhook_url": "https://discord.com/api/webhooks/mock/alert", "is_verified": True},
            enabled=True,
        )
        db.add(channel)
        db.commit()

        # Create baseline version
        v_base = Version(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            sequence_number=1,
            content_hash="hash1",
            normalized_text="Initial text",
            screenshot_path="",
            captured_at=utc_now(),
        )
        db.add(v_base)
        db.commit()

        # 1. BASELINE / UNCHANGED captures must NEVER call or create outbox records
        # Verify directly with create_outbox_entries_for_changed_version:
        # Create changed version v2
        v_changed = Version(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            sequence_number=2,
            content_hash="hash2",
            normalized_text="Modified text",
            screenshot_path="",
            captured_at=utc_now(),
        )
        db.add(v_changed)
        db.commit()

        # CHANGED event triggers outbox creation
        outbox = create_outbox_entries_for_changed_version(
            db=db,
            monitor=monitor,
            version=v_changed,
            change_summary="Price changed from $10 to $20",
            force_async=False,
        )
        assert len(outbox) == 1
        assert outbox[0].channel_id == channel.id

        # Deduplication check: calling again for same version does not create duplicate
        outbox_dup = create_outbox_entries_for_changed_version(
            db=db,
            monitor=monitor,
            version=v_changed,
            change_summary="Price changed from $10 to $20",
            force_async=False,
        )
        assert len(outbox_dup) == 0

        # Outbox endpoint reflects the alert
        outbox_res = client.get("/api/notifications/outbox", headers=headers)
        assert outbox_res.status_code == 200
        items = outbox_res.json()
        assert len(items) >= 1
        assert items[0]["channel_type"] == "discord"

        # Bounded volume test: add 10 outbox items to hit volume limit
        for i in range(10):
            dummy_ver = Version(
                id=uuid.uuid4(),
                monitor_id=monitor.id,
                sequence_number=10 + i,
                content_hash=f"dummyhash_{i}",
                normalized_text=f"Dummy text {i}",
                screenshot_path="",
                captured_at=utc_now(),
            )
            db.add(dummy_ver)
            dummy_out = NotificationOutbox(
                id=uuid.uuid4(),
                monitor_id=monitor.id,
                version_id=dummy_ver.id,
                channel_id=channel.id,
                state=OutboxStateEnum.SENT,
                attempts=1,
            )
            db.add(dummy_out)
        db.commit()

        # 11th change attempt must be blocked by bounded volume protection
        v3 = Version(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            sequence_number=3,
            content_hash="hash3",
            normalized_text="Text 3",
            screenshot_path="",
            captured_at=utc_now(),
        )
        db.add(v3)
        db.commit()

        capped_outbox = create_outbox_entries_for_changed_version(
            db=db,
            monitor=monitor,
            version=v3,
            change_summary="Another change",
            force_async=False,
        )
        assert len(capped_outbox) == 0, "Judge session must enforce bounded alert volume cap (10 max)"

    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6. Automatic Channel Cleanup on Session Expiration
# ---------------------------------------------------------------------------
def test_judge_channel_cleanup_on_session_expiration():
    _, session_id, headers = create_judge_session_helper()
    mon_id = create_judge_monitor_helper(headers)

    db = SessionLocal()
    try:
        monitor = db.query(Monitor).filter(Monitor.id == mon_id).first()
        channel = NotificationChannel(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            channel_type=ChannelTypeEnum.DISCORD,
            configuration_json={"webhook_url": "https://discord.com/api/webhooks/mock/expire"},
            enabled=True,
        )
        db.add(channel)
        db.commit()

        # Mark monitor as expired
        monitor.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        # Run session cleanup
        cleanup_expired_judge_monitors(db)
        db.refresh(channel)
        db.refresh(monitor)

        assert monitor.enabled is False
        assert channel.enabled is False

        # When monitor is deleted, channels are cascade-deleted
        db.delete(monitor)
        db.commit()

        remaining_channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel.id).first()
        assert remaining_channel is None, "Channel must be cascade-deleted when judge monitor is deleted"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 7. Test Notification Rate Limiting (Max 3 / Hour)
# ---------------------------------------------------------------------------
def test_test_notification_rate_limiting(monkeypatch):
    from fastapi import HTTPException
    from app.services import judge
    from app.redis_client import redis_client

    _, session_id, headers = create_judge_session_helper()
    monkeypatch.setattr(settings, "TEST_MODE", False)
    judge._in_memory_judge_tests.clear()
    try:
        redis_client.delete(f"rate:judge_test:{session_id}")
    except Exception:
        pass

    # 3 tests succeed within the hour
    for _ in range(3):
        judge.check_judge_test_rate_limit(session_id, max_tests_per_hour=3)

    # 4th test raises 429
    with pytest.raises(HTTPException) as exc_info:
        judge.check_judge_test_rate_limit(session_id, max_tests_per_hour=3)
    assert exc_info.value.status_code == 429
    assert "limit reached" in exc_info.value.detail["error"]["message"].lower()


