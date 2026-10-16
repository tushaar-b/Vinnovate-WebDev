import uuid
import time
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import get_db, SessionLocal
from app.models.models import (
    Monitor,
    CheckRun,
    CheckRunStateEnum,
    Version,
    VersionArtifact,
)
from app.services.auth import create_judge_session_token
from app.services.judge import cleanup_expired_judge_monitors
from scheduler import run_scheduler_tick

client = TestClient(app)

ADMIN_PASSWORD = "test_judge_admin_password_123"


@pytest.fixture(autouse=True)
def setup_auth_environment(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setattr(settings, "TEST_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "TEST_MODE", True)


def get_admin_token() -> str:
    res = client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert res.status_code == 200
    return res.json()["token"]


# ---------------------------------------------------------------------------
# 1. Public Session Creation Without Admin Credentials
# ---------------------------------------------------------------------------
def test_public_session_creation_without_admin_credentials():
    res = client.post("/api/judge/session")
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert "token" in data
    assert "expires_at" in data
    assert data["max_monitors"] == 2
    assert data["monitor_count"] == 0

    token = data["token"]
    # Verify status with token
    status_res = client.get("/api/judge/session/status", headers={"Authorization": f"Bearer {token}"})
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["active"] is True
    assert status_data["session_id"] == data["session_id"]


# ---------------------------------------------------------------------------
# 2. Judge Can Add Safe Public URL and Quota (Max 2) Enforced
# ---------------------------------------------------------------------------
def test_judge_monitor_creation_and_quota_limit():
    # Create judge session
    res = client.post("/api/judge/session")
    token = res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Monitor 1: Safe public URL
    m1_res = client.post(
        "/api/monitors",
        headers=headers,
        json={"name": "Judge Target 1", "url": "https://example.com/page1", "interval_minutes": 15},
    )
    assert m1_res.status_code == 201
    m1_data = m1_res.json()
    m1_id = m1_data["id"]

    # Monitor 2: Safe public URL (min interval enforced to 15)
    m2_res = client.post(
        "/api/monitors",
        headers=headers,
        json={"name": "Judge Target 2", "url": "https://example.com/page2", "interval_minutes": 5},
    )
    assert m2_res.status_code == 201
    m2_data = m2_res.json()
    assert m2_data["interval_minutes"] >= 15

    # Monitor 3: Exceeds 2 monitor quota -> 400 Bad Request
    m3_res = client.post(
        "/api/monitors",
        headers=headers,
        json={"name": "Judge Target 3", "url": "https://example.com/page3", "interval_minutes": 15},
    )
    assert m3_res.status_code == 400
    assert "maximum of 2 monitors" in m3_res.json()["detail"]["error"]["message"].lower()

    # Deleting 1 monitor frees up a slot
    del_res = client.delete(f"/api/monitors/{m1_id}", headers=headers)
    assert del_res.status_code == 204
    # Now creating another monitor succeeds
    m4_res = client.post(
        "/api/monitors",
        headers=headers,
        json={"name": "Judge Target 4", "url": "https://example.com/page4", "interval_minutes": 15},
    )
    assert m4_res.status_code == 201

    # Clean up
    client.delete(f"/api/monitors/{m2_data['id']}", headers=headers)
    client.delete(f"/api/monitors/{m4_res.json()['id']}", headers=headers)


# ---------------------------------------------------------------------------
# 3. Judge Isolation: Judge A Cannot Access Judge B's Resources
# ---------------------------------------------------------------------------
def test_cross_judge_isolation():
    # Session A
    res_a = client.post("/api/judge/session")
    token_a = res_a.json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Session B
    res_b = client.post("/api/judge/session")
    token_b = res_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Judge A creates monitor
    m_res = client.post(
        "/api/monitors",
        headers=headers_a,
        json={"name": "Judge A Monitor", "url": "https://example.com/target-a", "interval_minutes": 15},
    )
    assert m_res.status_code == 201
    mon_a_id = m_res.json()["id"]

    # Judge B lists monitors: mon_a_id MUST NOT be in list
    list_b = client.get("/api/monitors", headers=headers_b)
    assert list_b.status_code == 200
    b_ids = [item["id"] for item in list_b.json()["items"]]
    assert mon_a_id not in b_ids

    # Judge B direct access to Judge A's monitor returns 404 (not 403, preventing enumeration)
    assert client.get(f"/api/monitors/{mon_a_id}", headers=headers_b).status_code == 404
    assert client.delete(f"/api/monitors/{mon_a_id}", headers=headers_b).status_code == 404
    assert client.post(f"/api/monitors/{mon_a_id}/checks", headers=headers_b).status_code == 404
    assert client.get(f"/api/monitors/{mon_a_id}/checks", headers=headers_b).status_code == 404
    assert client.get(f"/api/monitors/{mon_a_id}/versions", headers=headers_b).status_code == 404
    assert client.get(f"/api/monitors/{mon_a_id}/picker", headers=headers_b).status_code == 404
    assert client.put(f"/api/monitors/{mon_a_id}/rules", headers=headers_b, json={"rules": []}).status_code == 404
    dummy_vid = str(uuid.uuid4())
    assert client.get(f"/api/monitors/{mon_a_id}/compare?from={dummy_vid}&to={dummy_vid}", headers=headers_b).status_code == 404

    # Clean up
    client.delete(f"/api/monitors/{mon_a_id}", headers=headers_a)


# ---------------------------------------------------------------------------
# 4. Judge Cannot Access Admin Resources or Privileged Settings
# ---------------------------------------------------------------------------
def test_judge_cannot_access_admin_monitors_or_settings():
    admin_token = get_admin_token()
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    # Admin creates monitor
    admin_mon_res = client.post(
        "/api/monitors",
        headers=headers_admin,
        json={"name": "Production Admin Monitor", "url": "https://example.com/admin-target", "interval_minutes": 15},
    )
    assert admin_mon_res.status_code == 201
    admin_mon_id = admin_mon_res.json()["id"]

    # Judge session
    judge_res = client.post("/api/judge/session")
    token_judge = judge_res.json()["token"]
    headers_judge = {"Authorization": f"Bearer {token_judge}"}

    # Judge cannot see admin monitor in list
    judge_monitors = client.get("/api/monitors", headers=headers_judge).json()["items"]
    assert admin_mon_id not in [m["id"] for m in judge_monitors]

    # Judge direct access to admin monitor returns 404
    assert client.get(f"/api/monitors/{admin_mon_id}", headers=headers_judge).status_code == 404
    assert client.delete(f"/api/monitors/{admin_mon_id}", headers=headers_judge).status_code == 404

    # Judge access to privileged notification settings returns 403 Forbidden
    assert client.get("/api/settings/notifications", headers=headers_judge).status_code == 403
    assert client.put(
        "/api/settings/notifications/discord",
        headers=headers_judge,
        json={"enabled": True, "configuration": {"webhook_url": "https://discord.com/api/webhooks/123/abc"}},
    ).status_code == 403
    assert client.post(
        "/api/settings/notifications/discord/test",
        headers=headers_judge,
        json={},
    ).status_code == 403

    # Clean up admin monitor
    client.delete(f"/api/monitors/{admin_mon_id}", headers=headers_admin)


# ---------------------------------------------------------------------------
# 5. Manual Check Rate Limit (Max 3 / hr)
# ---------------------------------------------------------------------------
def test_judge_manual_check_rate_limit():
    res = client.post("/api/judge/session")
    token = res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    mon_res = client.post(
        "/api/monitors",
        headers=headers,
        json={"name": "Rate Limit Target", "url": "https://example.com/rate-test", "interval_minutes": 15},
    )
    assert mon_res.status_code == 201
    mon_id = mon_res.json()["id"]

    # Manual check 1, 2, 3 succeed
    for i in range(3):
        c_res = client.post(f"/api/monitors/{mon_id}/checks", headers=headers)
        assert c_res.status_code == 202

    # Manual check 4 returns 429 Too Many Requests
    c4_res = client.post(f"/api/monitors/{mon_id}/checks", headers=headers)
    assert c4_res.status_code == 429
    assert "maximum 3 manual checks" in c4_res.json()["detail"]["error"]["message"].lower()

    # Clean up
    client.delete(f"/api/monitors/{mon_id}", headers=headers)


# ---------------------------------------------------------------------------
# 6. SSRF Protection Enforced on Judge Monitor Creation
# ---------------------------------------------------------------------------
def test_ssrf_protection_for_judge_creation():
    res = client.post("/api/judge/session")
    token = res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Loopback / internal IPs blocked
    blocked_urls = [
        "http://127.0.0.1:8000/internal",
        "http://localhost:8000/test",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/admin",
        "http://192.168.1.1/",
    ]
    for b_url in blocked_urls:
        bad_res = client.post(
            "/api/monitors",
            headers=headers,
            json={"name": "SSRF Attempt", "url": b_url, "interval_minutes": 15},
        )
        assert bad_res.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 7. Expired Judge Session & Scheduler Cleanup
# ---------------------------------------------------------------------------
def test_expired_judge_monitor_scheduler_cleanup():
    db = SessionLocal()
    try:
        # Create an expired judge session monitor directly in DB
        expired_session_id = f"test_expired_{uuid.uuid4().hex[:12]}"
        expired_monitor = Monitor(
            id=uuid.uuid4(),
            name="Expired Judge Monitor",
            url="https://example.com/expired",
            canonical_url="https://example.com/expired",
            interval_minutes=15,
            enabled=True,
            judge_session_id=expired_session_id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            next_check_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db.add(expired_monitor)
        db.commit()

        # Run scheduler cleanup
        cleaned = cleanup_expired_judge_monitors(db)
        assert cleaned >= 1

        db.refresh(expired_monitor)
        assert expired_monitor.enabled is False

        # Verify expired token is rejected
        expired_token = create_judge_session_token(expired_session_id, expires_in_seconds=-10)
        exp_res = client.get("/api/monitors", headers={"Authorization": f"Bearer {expired_token}"})
        assert exp_res.status_code == 401

    finally:
        db.close()
