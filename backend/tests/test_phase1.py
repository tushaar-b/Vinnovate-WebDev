import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.security import validate_target_url, canonicalize_url, SecurityValidationError
from app.services.browser import capture_page, BrowserCaptureError
from app.services.checker import execute_check
from app.database import SessionLocal
from app.models.models import Monitor, CheckRun, Version, CheckRunStateEnum, MonitorStatusEnum, SensitivityEnum

client = TestClient(app)


# -------------------------------------------------------------------------
# 1. URL & SSRF Validation Tests
# -------------------------------------------------------------------------

def test_public_url_acceptance():
    safe, reason = validate_target_url("https://example.com")
    assert safe is True, f"Expected safe URL to pass, got: {reason}"

    safe, reason = validate_target_url("http://example.org/news?page=1")
    assert safe is True


def test_invalid_scheme_rejection():
    for bad_scheme in ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "data:text/html,test"]:
        safe, reason = validate_target_url(bad_scheme)
        assert safe is False
        assert "scheme" in reason.lower()


def test_embedded_credentials_rejection():
    safe, reason = validate_target_url("https://admin:password@example.com")
    assert safe is False
    assert "authentication credentials" in reason.lower()


def test_nonstandard_ports_rejection():
    for bad_port in [22, 25, 3306, 5432, 6379, 8080]:
        safe, reason = validate_target_url(f"http://example.com:{bad_port}")
        assert safe is False
        assert "non-standard port" in reason.lower()


def test_localhost_and_loopback_rejection():
    for host in ["http://127.0.0.1", "http://127.0.0.2:80", "http://localhost", "http://[::1]"]:
        safe, reason = validate_target_url(host)
        assert safe is False, f"Expected {host} to be rejected"


def test_private_network_ips_rejection():
    for private in [
        "http://10.0.0.1",
        "http://10.254.1.1",
        "http://172.16.0.1",
        "http://172.31.255.255",
        "http://192.168.1.1",
        "http://192.168.100.5",
        "http://100.64.0.1",
    ]:
        safe, reason = validate_target_url(private)
        assert safe is False, f"Expected {private} to be rejected"
        assert "prohibited or private" in reason.lower()


def test_cloud_metadata_rejection():
    for meta in [
        "http://169.254.169.254",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal",
    ]:
        safe, reason = validate_target_url(meta)
        assert safe is False
        assert "prohibited" in reason.lower() or "metadata" in reason.lower()


def test_url_canonicalization():
    url1 = "HTTP://Example.com:80/path/to//page?b=2&a=1"
    canon = canonicalize_url(url1)
    assert canon == "http://example.com/path/to/page?a=1&b=2"


# -------------------------------------------------------------------------
# 2. Monitor CRUD Endpoints & Input Validation
# -------------------------------------------------------------------------

def test_monitor_create_and_validation():
    # 1. Reject private IP
    res_bad = client.post(
        "/api/monitors",
        json={"name": "Bad Monitor", "url": "http://192.168.1.1", "interval_minutes": 15},
    )
    assert res_bad.status_code == 400
    assert res_bad.json()["detail"]["error"]["code"] == "BLOCKED_TARGET"

    # 2. Reject invalid interval (< min allowed)
    res_interval = client.post(
        "/api/monitors",
        json={"name": "Bad Interval", "url": "https://example.com", "interval_minutes": 0},
    )
    assert res_interval.status_code == 422

    # 3. Create valid monitor
    res_ok = client.post(
        "/api/monitors",
        json={
            "name": "Example Test Site",
            "url": "https://example.com",
            "interval_minutes": 30,
            "sensitivity": "medium",
        },
    )
    assert res_ok.status_code == 201
    monitor_data = res_ok.json()
    monitor_id = monitor_data["id"]
    assert monitor_data["name"] == "Example Test Site"
    assert monitor_data["url"] == "https://example.com"
    assert monitor_data["canonical_url"] == "https://example.com/"
    assert monitor_data["interval_minutes"] == 30
    assert monitor_data["status"] == "pending"

    # 4. List monitors
    res_list = client.get("/api/monitors")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] >= 1
    found = any(m["id"] == monitor_id for m in data["items"])
    assert found is True

    # 5. Get monitor details
    res_detail = client.get(f"/api/monitors/{monitor_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == monitor_id

    # 6. Patch monitor
    res_patch = client.patch(
        f"/api/monitors/{monitor_id}",
        json={"name": "Updated Example Monitor", "interval_minutes": 60},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["name"] == "Updated Example Monitor"
    assert res_patch.json()["interval_minutes"] == 60

    # 7. Delete monitor
    res_del = client.delete(f"/api/monitors/{monitor_id}")
    assert res_del.status_code == 204

    # Verify deleted
    res_gone = client.get(f"/api/monitors/{monitor_id}")
    assert res_gone.status_code == 404


# -------------------------------------------------------------------------
# 3. Check Execution, Content Extraction & Screenshot Storage
# -------------------------------------------------------------------------

def test_fixture_check_execution_and_storage(monkeypatch):
    # Enable test mode to allow trusted fixture path
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        # Create monitor pointing to local fixture
        fixture_url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Fixture Product Test",
            url=fixture_url,
            canonical_url=canonicalize_url(fixture_url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # 1. Enqueue check via API (TestClient automatically executes BackgroundTasks)
        res_queue = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res_queue.status_code == 202
        queue_data = res_queue.json()
        assert queue_data["state"] == "queued"
        check_run_id = uuid.UUID(queue_data["check_run_id"])

        # 2. Verify check run completed with baseline
        db.expire_all()
        check_run = db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
        assert check_run is not None
        assert check_run.state == CheckRunStateEnum.BASELINE
        assert check_run.http_status == 200
        assert check_run.duration_ms is not None
        assert check_run.content_hash is not None
        assert len(check_run.content_hash) == 64

        # 4. Verify version created
        version = db.query(Version).filter(Version.monitor_id == monitor.id).first()
        assert version is not None
        assert version.sequence_number == 1
        assert "AcuTime Precision Chronometer 400" in version.normalized_text
        assert "$4999" in version.normalized_text
        assert version.screenshot_path.endswith(".png")

        # 5. Verify monitor status updated
        monitor_updated = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        assert monitor_updated.status == MonitorStatusEnum.OK
        assert monitor_updated.last_checked_at is not None
        assert monitor_updated.last_changed_at is not None

        # 6. Verify screenshot endpoint returns real PNG bytes
        res_screenshot = client.get(f"/api/versions/{version.id}/screenshot")
        assert res_screenshot.status_code == 200
        assert res_screenshot.headers["content-type"] == "image/png"
        assert len(res_screenshot.content) > 1000
        # Check PNG header magic bytes
        assert res_screenshot.content[:8] == b"\x89PNG\r\n\x1a\n"

        # 7. Verify versions list endpoint
        res_versions = client.get(f"/api/monitors/{monitor.id}/versions")
        assert res_versions.status_code == 200
        v_list = res_versions.json()["items"]
        assert len(v_list) == 1
        assert v_list[0]["id"] == str(version.id)
        assert "$4999" in v_list[0]["short_preview"]

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 4. Error Classification & SSRF Redirect Blocking
# -------------------------------------------------------------------------

def test_ssrf_malicious_redirect_blocked(monkeypatch):
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        # Fixture endpoint redirects to AWS metadata (169.254.169.254)
        malicious_url = f"http://127.0.0.1:{settings.API_PORT}/fixture/redirect-unsafe"
        monitor = Monitor(
            name="Malicious Redirect Target",
            url=malicious_url,
            canonical_url=canonicalize_url(malicious_url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        check_run_id = uuid.uuid4()
        check_run = CheckRun(
            id=check_run_id,
            monitor_id=monitor.id,
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            state=CheckRunStateEnum.QUEUED,
        )
        db.add(check_run)
        db.commit()

        # Execute check
        execute_check(check_run_id)

        db.expire_all()
        check_run = db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
        assert check_run.state == CheckRunStateEnum.BLOCKED
        assert check_run.error_code == "BLOCKED_TARGET"

        monitor_updated = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        assert monitor_updated.status == MonitorStatusEnum.BLOCKED
        assert "blocked" in monitor_updated.last_error.lower() or "prohibited" in monitor_updated.last_error.lower()

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


def test_http_500_error_handling(monkeypatch):
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        error_url = f"http://127.0.0.1:{settings.API_PORT}/fixture/error500"
        monitor = Monitor(
            name="Error 500 Target",
            url=error_url,
            canonical_url=canonicalize_url(error_url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        check_run_id = uuid.uuid4()
        check_run = CheckRun(
            id=check_run_id,
            monitor_id=monitor.id,
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            state=CheckRunStateEnum.QUEUED,
        )
        db.add(check_run)
        db.commit()

        execute_check(check_run_id)

        db.expire_all()
        check_run = db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
        assert check_run.state == CheckRunStateEnum.ERROR
        assert check_run.error_code == "HTTP_5XX"
        assert check_run.http_status == 500

        monitor_updated = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        assert monitor_updated.status == MonitorStatusEnum.ERROR

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()
