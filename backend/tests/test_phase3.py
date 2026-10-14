import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.security import canonicalize_url
from app.services.checker import execute_check
from app.database import SessionLocal
from app.models.models import (
    Monitor,
    MonitorRule,
    CheckRun,
    Version,
    CheckRunStateEnum,
    MonitorStatusEnum,
    SensitivityEnum,
    RuleTypeEnum,
)

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. T05: Noise Filter & Ignore Selector
# -----------------------------------------------------------------------------

def test_ignore_selector_filters_timestamp_and_counter_noise(monkeypatch):
    """
    T05:
    When an ignore rule is configured for '#timestamp' or '#visitor-counter',
    modifying only the timestamp or counter noise does NOT create a new version.
    The check is recorded as UNCHANGED and version count remains stable.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url_v1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&timestamp=2026-10-14+00:00:00+UTC&visitors=100"
        monitor = Monitor(
            name="Ignore Selector Test Monitor",
            url=url_v1,
            canonical_url=canonicalize_url(url_v1),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Configure ignore rules for #timestamp and #visitor-counter
        rule_ts = MonitorRule(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            rule_type=RuleTypeEnum.IGNORE,
            css_selector="#timestamp",
            label="Noise Timestamp",
        )
        rule_vc = MonitorRule(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            rule_type=RuleTypeEnum.IGNORE,
            css_selector="#visitor-counter",
            label="Visitor Noise",
        )
        db.add_all([rule_ts, rule_vc])
        db.commit()

        # 1. Baseline check (v1)
        res1 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res1.status_code == 202

        db.expire_all()
        versions_1 = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_1) == 1
        assert "System Clock:" not in versions_1[0].normalized_text
        assert "Live Viewers:" not in versions_1[0].normalized_text

        # 2. Mutate ONLY the timestamp and visitor counter
        url_v2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&timestamp=2026-10-14+02:30:00+UTC&visitors=999"
        monitor.url = url_v2
        monitor.canonical_url = canonicalize_url(url_v2)
        db.commit()

        res2 = client.post(f"/api/monitors/{monitor.id}/checks")
        assert res2.status_code == 202
        check2_id = uuid.UUID(res2.json()["check_run_id"])

        db.expire_all()
        check2 = db.query(CheckRun).filter(CheckRun.id == check2_id).first()
        assert check2.state == CheckRunStateEnum.UNCHANGED

        # Version count MUST remain strictly 1
        versions_2 = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_2) == 1

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 2. T06: Watch Selector for Specific Element
# -----------------------------------------------------------------------------

def test_watch_selector_price_isolated_from_unrelated_banner(monkeypatch):
    """
    T06:
    When a watch rule is configured for '#price':
    1. Modifying the unrelated banner text results in UNCHANGED (0 new versions).
    2. Modifying the watched price element creates a CHANGED version (v2).
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url_initial = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&banner=Original+Banner"
        monitor = Monitor(
            name="Watch Price Only Monitor",
            url=url_initial,
            canonical_url=canonicalize_url(url_initial),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Configure watch rule on #price
        rule_price = MonitorRule(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            rule_type=RuleTypeEnum.WATCH,
            css_selector="#price",
            label="Product Price",
        )
        db.add(rule_price)
        db.commit()

        # 1. Baseline
        client.post(f"/api/monitors/{monitor.id}/checks")

        db.expire_all()
        v1 = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(v1) == 1
        assert v1[0].normalized_text.strip() == "$4999"

        # 2. Mutate unrelated banner -> MUST be UNCHANGED
        url_banner_change = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&banner=Flash+Sale+Active+Now"
        monitor.url = url_banner_change
        monitor.canonical_url = canonicalize_url(url_banner_change)
        db.commit()

        res_banner = client.post(f"/api/monitors/{monitor.id}/checks")
        check_b_id = uuid.UUID(res_banner.json()["check_run_id"])

        db.expire_all()
        check_b = db.query(CheckRun).filter(CheckRun.id == check_b_id).first()
        assert check_b.state == CheckRunStateEnum.UNCHANGED

        v_after_banner = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(v_after_banner) == 1

        # 3. Mutate watched price ($5999) -> MUST create CHANGED version (v2)
        url_price_change = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=5999&banner=Flash+Sale+Active+Now"
        monitor.url = url_price_change
        monitor.canonical_url = canonicalize_url(url_price_change)
        db.commit()

        res_price = client.post(f"/api/monitors/{monitor.id}/checks")
        check_p_id = uuid.UUID(res_price.json()["check_run_id"])

        db.expire_all()
        check_p = db.query(CheckRun).filter(CheckRun.id == check_p_id).first()
        assert check_p.state == CheckRunStateEnum.CHANGED

        v_after_price = db.query(Version).filter(Version.monitor_id == monitor.id).order_by(Version.sequence_number.asc()).all()
        assert len(v_after_price) == 2
        assert v_after_price[1].sequence_number == 2
        assert v_after_price[1].normalized_text.strip() == "$5999"

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 3. T07: Missing Watched Selector Error Handling
# -----------------------------------------------------------------------------

def test_missing_watch_selector_reports_error_and_preserves_baseline(monkeypatch):
    """
    T07:
    If a configured watch selector disappears or is missing on the target page,
    the check run is flagged with MISSING_SELECTOR error and the baseline is preserved.
    It does NOT create a false content change version.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Missing Selector Monitor",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline check before adding missing rule
        client.post(f"/api/monitors/{monitor.id}/checks")

        db.expire_all()
        v_base = db.query(Version).filter(Version.monitor_id == monitor.id).first()
        assert v_base is not None
        assert v_base.sequence_number == 1

        # Add a watch selector for an element that does NOT exist on the fixture
        rule_missing = MonitorRule(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            rule_type=RuleTypeEnum.WATCH,
            css_selector="#non-existent-element-xyz",
            label="Missing Element",
        )
        db.add(rule_missing)
        db.commit()

        # Trigger check -> MUST fail with MISSING_SELECTOR
        res = client.post(f"/api/monitors/{monitor.id}/checks")
        check_id = uuid.UUID(res.json()["check_run_id"])

        db.expire_all()
        check = db.query(CheckRun).filter(CheckRun.id == check_id).first()
        assert check.state == CheckRunStateEnum.ERROR
        assert check.error_code == "MISSING_SELECTOR"
        assert "not found" in check.error_message.lower()

        # Baseline version remains intact and count is still 1
        versions = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions) == 1
        assert versions[0].id == v_base.id

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 4. T11: Region Picker API & Selector Rules PUT
# -----------------------------------------------------------------------------

def test_picker_api_returns_elements_and_rules_put_endpoint(monkeypatch):
    """
    T11:
    Tests GET /api/monitors/{id}/picker endpoint returns valid screenshot URL,
    standard viewport dimensions (1440x900), and element rect geometry.
    Tests PUT /api/monitors/{id}/rules atomically updates monitor rules.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Picker API Test Monitor",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline check
        client.post(f"/api/monitors/{monitor.id}/checks")

        # Query picker endpoint
        res_picker = client.get(f"/api/monitors/{monitor.id}/picker")
        assert res_picker.status_code == 200
        data = res_picker.json()

        assert data["width"] == 1440
        assert data["height"] == 900
        assert data["screenshot_url"].startswith("/api/")
        assert len(data["elements"]) > 0

        # Verify returned screenshot_url resolves to HTTP 200 with valid PNG bytes
        res_img = client.get(data["screenshot_url"])
        assert res_img.status_code == 200
        assert res_img.headers["content-type"] == "image/png"
        assert res_img.content.startswith(b"\x89PNG\r\n\x1a\n")

        # Element rect checks
        first_el = data["elements"][0]
        assert "selector" in first_el
        assert "x" in first_el
        assert "y" in first_el
        assert "width" in first_el
        assert "height" in first_el
        assert first_el["width"] > 0
        assert first_el["height"] > 0

        # Test PUT /api/monitors/{id}/rules
        rules_payload = {
            "rules": [
                {"rule_type": "watch", "css_selector": "#price", "label": "Product Price"},
                {"rule_type": "ignore", "css_selector": "#timestamp", "label": "Clock Noise"},
            ]
        }
        res_rules = client.put(f"/api/monitors/{monitor.id}/rules", json=rules_payload)
        assert res_rules.status_code == 200
        saved_rules = res_rules.json()
        assert len(saved_rules) == 2
        assert saved_rules[0]["css_selector"] == "#price"
        assert saved_rules[0]["rule_type"] == "watch"
        assert saved_rules[1]["css_selector"] == "#timestamp"
        assert saved_rules[1]["rule_type"] == "ignore"

        # Verify in database
        db.expire_all()
        db_rules = db.query(MonitorRule).filter(MonitorRule.monitor_id == monitor.id).all()
        assert len(db_rules) == 2

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 5. Regression Tests for Region Picker & Failure Handling
# -----------------------------------------------------------------------------

def test_picker_screenshot_and_bounding_boxes_alignment_without_prior_version(monkeypatch):
    """
    Regression Test:
    Ensures GET /api/monitors/{id}/picker returns valid screenshot URL and aligned bounding boxes
    even when the monitor has NO prior versions.
    Validates that:
    1. screenshot_url returns HTTP 200 and valid PNG image bytes.
    2. PNG dimensions match 1440x900 viewport.
    3. All DOM bounding box coordinates are strictly within viewport boundaries.
    """
    import io
    from PIL import Image

    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Fresh Monitor Without Baseline",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Monitor has 0 versions
        assert len(monitor.versions) == 0

        # Request picker data
        res_picker = client.get(f"/api/monitors/{monitor.id}/picker")
        assert res_picker.status_code == 200
        picker_data = res_picker.json()

        assert picker_data["width"] == 1440
        assert picker_data["height"] == 900
        assert picker_data["screenshot_url"].startswith("/api/")

        # Verify screenshot URL returns HTTP 200 and valid PNG bytes
        res_screenshot = client.get(picker_data["screenshot_url"])
        assert res_screenshot.status_code == 200
        assert res_screenshot.headers["content-type"] == "image/png"
        assert res_screenshot.content.startswith(b"\x89PNG\r\n\x1a\n")

        # Verify actual image dimensions
        img = Image.open(io.BytesIO(res_screenshot.content))
        assert img.width == 1440
        assert img.height == 900

        # Verify bounding box elements fall within screenshot dimensions
        elements = picker_data["elements"]
        assert len(elements) > 0
        for el in elements:
            assert el["width"] > 0
            assert el["height"] > 0
            assert 0 <= el["x"] <= 1440
            assert 0 <= el["y"] <= 900
            assert el["x"] + el["width"] <= 1440
            assert el["y"] + el["height"] <= 900

        # Also verify dedicated picker screenshot endpoint
        res_dedicated = client.get(f"/api/monitors/{monitor.id}/picker/screenshot")
        assert res_dedicated.status_code == 200
        assert res_dedicated.headers["content-type"] == "image/png"

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


def test_watch_ignore_rules_persist_across_monitor_reloads(monkeypatch):
    """
    Regression Test:
    Ensures that watch and ignore rules configured via PUT /api/monitors/{id}/rules
    persist and are properly returned when re-fetching the monitor via GET /api/monitors/{id}.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Rules Persistence Monitor",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=30,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Save rules: 1 watch rule (#price) and 1 ignore rule (#timestamp)
        payload = {
            "rules": [
                {"rule_type": "watch", "css_selector": "#price", "label": "Watch Product Price"},
                {"rule_type": "ignore", "css_selector": "#timestamp", "label": "Ignore System Clock"},
            ]
        }
        res_put = client.put(f"/api/monitors/{monitor.id}/rules", json=payload)
        assert res_put.status_code == 200

        # Reload monitor via GET /api/monitors/{id}
        res_get = client.get(f"/api/monitors/{monitor.id}")
        assert res_get.status_code == 200
        monitor_detail = res_get.json()

        assert len(monitor_detail["rules"]) == 2
        rule_map = {r["css_selector"]: r for r in monitor_detail["rules"]}
        assert "#price" in rule_map
        assert rule_map["#price"]["rule_type"] == "watch"
        assert rule_map["#price"]["label"] == "Watch Product Price"
        assert "#timestamp" in rule_map
        assert rule_map["#timestamp"]["rule_type"] == "ignore"
        assert rule_map["#timestamp"]["label"] == "Ignore System Clock"

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


def test_picker_failure_states_handled_without_blank_panel(monkeypatch):
    """
    Regression Test:
    When a monitor points to an unreachable or error page,
    GET /api/monitors/{id}/picker returns a clean structured error (HTTP 502)
    rather than an unhandled 500 server crash.
    """
    monkeypatch.setattr(settings, "TEST_MODE", True)

    db = SessionLocal()
    try:
        # Fixture returning 500 error
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/error500"
        monitor = Monitor(
            name="Error Target Monitor",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        res_picker = client.get(f"/api/monitors/{monitor.id}/picker")
        assert res_picker.status_code == 502
        err_json = res_picker.json()
        assert "detail" in err_json
        assert "error" in err_json["detail"]
        assert "Failed to load target webpage for picker" in err_json["detail"]["error"]["message"]

        db.delete(monitor)
        db.commit()
    finally:
        db.close()
