import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.security import validate_target_url, canonicalize_url
from app.services.checker import execute_check
from app.services.diff import compute_text_diff, compute_screenshot_diff
from app.database import SessionLocal
from app.models.models import Monitor, CheckRun, Version, CheckRunStateEnum, MonitorStatusEnum, SensitivityEnum

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Baseline Creation & Unchanged Idempotency
# -----------------------------------------------------------------------------

def test_first_capture_creates_baseline_and_second_identical_is_unchanged(monkeypatch):
    """
    T02 & T03:
    1. First successful check creates exactly one baseline version (v1).
    2. Identical second check run records UNCHANGED state and does NOT create a new version.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        # Create monitor pointing to initial product fixture
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&title=AcuTime+400"
        monitor = Monitor(
            name="Baseline & Unchanged Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # 1. First check -> BASELINE
        res1 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res1.status_code == 202
        check1_id = uuid.UUID(res1.json()["check_run_id"])

        db.expire_all()
        check1 = db.query(CheckRun).filter(CheckRun.id == check1_id).first()
        assert check1 is not None
        assert check1.state == CheckRunStateEnum.BASELINE
        assert check1.content_hash is not None

        versions_after_first = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_after_first) == 1
        assert versions_after_first[0].sequence_number == 1
        baseline_hash = versions_after_first[0].content_hash

        # 2. Second check with IDENTICAL content -> UNCHANGED
        res2 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res2.status_code == 202
        check2_id = uuid.UUID(res2.json()["check_run_id"])

        db.expire_all()
        check2 = db.query(CheckRun).filter(CheckRun.id == check2_id).first()
        assert check2 is not None
        assert check2.state == CheckRunStateEnum.UNCHANGED
        assert check2.content_hash == baseline_hash

        # Versions count must strictly remain 1
        versions_after_second = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_after_second) == 1

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 2. Price, Title & Availability Change Detection
# -----------------------------------------------------------------------------

def test_price_change_creates_version_2(monkeypatch):
    """
    T04:
    A change in monitored content (price: 4999 -> 5499) creates exactly one new version (v2).
    A subsequent check with identical price (5499) creates no additional version.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url_v1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999"
        monitor = Monitor(
            name="Price Change Monitor",
            url=url_v1,
            canonical_url=canonicalize_url(url_v1),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline check (v1)
        res1 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res1.status_code == 202

        db.expire_all()
        versions = db.query(Version).filter(Version.monitor_id == monitor.id).order_by(Version.sequence_number.asc()).all()
        assert len(versions) == 1
        assert "$4999" in versions[0].normalized_text

        # Mutate monitor target to new price ($5499)
        url_v2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=5499"
        monitor.url = url_v2
        monitor.canonical_url = canonicalize_url(url_v2)
        db.commit()

        # Execute check -> CHANGED (v2)
        res2 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res2.status_code == 202
        check2_id = uuid.UUID(res2.json()["check_run_id"])

        db.expire_all()
        check2 = db.query(CheckRun).filter(CheckRun.id == check2_id).first()
        assert check2.state == CheckRunStateEnum.CHANGED

        versions2 = db.query(Version).filter(Version.monitor_id == monitor.id).order_by(Version.sequence_number.asc()).all()
        assert len(versions2) == 2
        assert versions2[1].sequence_number == 2
        assert "$5499" in versions2[1].normalized_text

        # Monitor status should be CHANGED
        monitor_updated = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        assert monitor_updated.status == MonitorStatusEnum.CHANGED

        # Check identical v2 again -> UNCHANGED, count remains 2
        res3 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res3.status_code == 202
        check3_id = uuid.UUID(res3.json()["check_run_id"])

        db.expire_all()
        check3 = db.query(CheckRun).filter(CheckRun.id == check3_id).first()
        assert check3.state == CheckRunStateEnum.UNCHANGED

        versions3 = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions3) == 2

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


def test_title_and_availability_changes_detected(monkeypatch):
    """
    Monitors capture changes in product title and stock availability as distinct versions.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url_base = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?title=Base+Title&availability=In+Stock"
        monitor = Monitor(
            name="Title & Availability Monitor",
            url=url_base,
            canonical_url=canonicalize_url(url_base),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline
        client.post(f"/api/monitors/{monitor.id}/checks")

        # Change availability to "Out of Stock"
        url_oos = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?title=Base+Title&availability=Out+of+Stock"
        monitor.url = url_oos
        monitor.canonical_url = canonicalize_url(url_oos)
        db.commit()

        res_oos = client.post(f"/api/monitors/{monitor.id}/checks")
        check_oos_id = uuid.UUID(res_oos.json()["check_run_id"])

        db.expire_all()
        check_oos = db.query(CheckRun).filter(CheckRun.id == check_oos_id).first()
        assert check_oos.state == CheckRunStateEnum.CHANGED

        # Change title to "Pro Edition Title"
        url_title = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?title=Pro+Edition+Title&availability=Out+of+Stock"
        monitor.url = url_title
        monitor.canonical_url = canonicalize_url(url_title)
        db.commit()

        res_title = client.post(f"/api/monitors/{monitor.id}/checks")
        check_title_id = uuid.UUID(res_title.json()["check_run_id"])

        db.expire_all()
        check_title = db.query(CheckRun).filter(CheckRun.id == check_title_id).first()
        assert check_title.state == CheckRunStateEnum.CHANGED

        versions = db.query(Version).filter(Version.monitor_id == monitor.id).order_by(Version.sequence_number.asc()).all()
        assert len(versions) == 3
        assert versions[0].sequence_number == 1
        assert versions[1].sequence_number == 2
        assert versions[2].sequence_number == 3
        assert "Out of Stock" in versions[1].normalized_text
        assert "Pro Edition Title" in versions[2].normalized_text

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 3. Error / Blocked Status Preserves Baseline
# -----------------------------------------------------------------------------

def test_http_500_and_blocked_preserve_baseline_version(monkeypatch):
    """
    T08:
    A transient HTTP 500 or HTTP 403 / anti-bot block does NOT create a version,
    and preserves the existing valid baseline version.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url_valid = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Error Resilience Test",
            url=url_valid,
            canonical_url=canonicalize_url(url_valid),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # 1. Baseline
        client.post(f"/api/monitors/{monitor.id}/checks")

        db.expire_all()
        v_baseline = db.query(Version).filter(Version.monitor_id == monitor.id).first()
        assert v_baseline is not None
        assert v_baseline.sequence_number == 1

        # 2. Simulate HTTP 500
        url_500 = f"http://127.0.0.1:{settings.API_PORT}/fixture/error500"
        monitor.url = url_500
        monitor.canonical_url = canonicalize_url(url_500)
        db.commit()

        res_500 = client.post(f"/api/monitors/{monitor.id}/checks")
        check_500_id = uuid.UUID(res_500.json()["check_run_id"])

        db.expire_all()
        check_500 = db.query(CheckRun).filter(CheckRun.id == check_500_id).first()
        assert check_500.state == CheckRunStateEnum.ERROR
        assert check_500.error_code == "HTTP_5XX"

        # Versions count must strictly remain 1 and baseline preserved
        versions_after_500 = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_after_500) == 1
        assert versions_after_500[0].id == v_baseline.id

        # 3. Simulate HTTP 403 / Blocked
        url_blocked = f"http://127.0.0.1:{settings.API_PORT}/fixture/blocked"
        monitor.url = url_blocked
        monitor.canonical_url = canonicalize_url(url_blocked)
        db.commit()

        res_blocked = client.post(f"/api/monitors/{monitor.id}/checks")
        check_blocked_id = uuid.UUID(res_blocked.json()["check_run_id"])

        db.expire_all()
        check_blocked = db.query(CheckRun).filter(CheckRun.id == check_blocked_id).first()
        assert check_blocked.state == CheckRunStateEnum.BLOCKED

        # Versions count still strictly 1
        versions_after_blocked = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_after_blocked) == 1
        assert versions_after_blocked[0].id == v_baseline.id

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 4. Two-Version Comparison (Nonadjacent & Text Diff)
# -----------------------------------------------------------------------------

def test_compare_nonadjacent_versions_and_text_diff(monkeypatch):
    """
    T13:
    Compare Version 1 and Version 3 (nonadjacent).
    Text diff correctly identifies additions and removals.
    Visual diff returns valid viewable image URLs and artifacts.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        # Create 3 versions:
        # v1: price 1000, title Alpha
        # v2: price 2000, title Beta
        # v3: price 3000, title Gamma
        url_v1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=1000&title=Alpha"
        monitor = Monitor(
            name="Nonadjacent Compare Test",
            url=url_v1,
            canonical_url=canonicalize_url(url_v1),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline v1
        client.post(f"/api/monitors/{monitor.id}/checks")

        # v2
        url_v2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=2000&title=Beta"
        monitor.url = url_v2
        monitor.canonical_url = canonicalize_url(url_v2)
        db.commit()
        client.post(f"/api/monitors/{monitor.id}/checks")

        # v3
        url_v3 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=3000&title=Gamma"
        monitor.url = url_v3
        monitor.canonical_url = canonicalize_url(url_v3)
        db.commit()
        client.post(f"/api/monitors/{monitor.id}/checks")

        db.expire_all()
        versions = db.query(Version).filter(Version.monitor_id == monitor.id).order_by(Version.sequence_number.asc()).all()
        assert len(versions) == 3
        v1, v2, v3 = versions[0], versions[1], versions[2]

        # Call compare endpoint between v1 and v3 (nonadjacent!)
        res_compare = client.get(f"/api/monitors/{monitor.id}/compare?from={v1.id}&to={v3.id}")
        assert res_compare.status_code == 200
        diff_data = res_compare.json()

        assert diff_data["old_version"]["sequence_number"] == 1
        assert diff_data["new_version"]["sequence_number"] == 3
        assert diff_data["image_old_url"] == f"/api/versions/{v1.id}/screenshot"
        assert diff_data["image_new_url"] == f"/api/versions/{v3.id}/screenshot"
        assert diff_data["image_diff_url"] is not None

        # Verify text diff structure: additions and removals
        text_diff = diff_data["text_diff"]
        assert len(text_diff) > 0

        added_texts = [d["text"] for d in text_diff if d["kind"] == "add"]
        removed_texts = [d["text"] for d in text_diff if d["kind"] == "remove"]

        # v1 had $1000 and Alpha; v3 has $3000 and Gamma
        assert any("$1000" in t for t in removed_texts)
        assert any("Alpha" in t for t in removed_texts)
        assert any("$3000" in t for t in added_texts)
        assert any("Gamma" in t for t in added_texts)

        # Verify visual diff endpoint returns real PNG bytes
        diff_img_url = diff_data["image_diff_url"]
        res_img = client.get(diff_img_url)
        assert res_img.status_code == 200
        assert res_img.headers["content-type"] == "image/png"
        assert res_img.content[:8] == b"\x89PNG\r\n\x1a\n"

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 5. Concurrency & Uniqueness Protection
# -----------------------------------------------------------------------------

def test_database_uniqueness_prevents_duplicate_sequence(monkeypatch):
    """
    Enforces that the database UniqueConstraint("monitor_id", "sequence_number")
    and transaction serialisation prevent duplicate version snapshots.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Uniqueness Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline
        client.post(f"/api/monitors/{monitor.id}/checks")

        db.expire_all()
        versions = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions) == 1

        # Attempt to insert a version with duplicate sequence_number 1 directly
        from sqlalchemy.exc import IntegrityError
        dup_version = Version(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            sequence_number=1,  # Duplicate sequence number!
            content_hash="dummyhash",
            normalized_text="dummy text",
            screenshot_path="dummy.png",
        )
        db.add(dup_version)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 6. SSRF Localhost Bypass Security Audit
# -----------------------------------------------------------------------------

def test_arbitrary_localhost_and_ports_remain_strictly_blocked():
    """
    Phase 1 carry-forward verification:
    Verify that localhost fixture exceptions are limited to explicit test mode,
    exact /fixture paths and trusted port. Arbitrary localhost URLs remain blocked.
    """
    # 1. Arbitrary localhost path on API port
    safe, reason = validate_target_url(f"http://127.0.0.1:{settings.API_PORT}/admin/secrets")
    assert safe is False
    assert any(w in reason.lower() for w in ["prohibited", "private", "non-standard", "prohibit"])

    # 2. Arbitrary port on 127.0.0.1
    safe, reason = validate_target_url("http://127.0.0.1:8080/fixture/product")
    assert safe is False
    assert "non-standard port" in reason.lower()

    # 3. Arbitrary internal target on port 80 (standard port)
    safe, reason = validate_target_url("http://127.0.0.1/admin/keys")
    assert safe is False
    assert "prohibited or private" in reason.lower()

