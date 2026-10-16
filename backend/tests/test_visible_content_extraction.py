import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.browser import capture_page, VISIBLE_TEXT_EXTRACTION_JS
from app.services.normalizer import normalize_text, calculate_content_hash
from app.services.diff import compute_text_diff
from app.models.models import (
    Monitor,
    Version,
    CheckRun,
    CheckRunStateEnum,
    MonitorStatusEnum,
    RuleTypeEnum,
)
from app.services.checker import execute_check

import threading
import time
import uvicorn

client = TestClient(app)



# -----------------------------------------------------------------------------
# 1. Direct Browser Extraction Tests with Playwright
# -----------------------------------------------------------------------------

def test_identical_visible_content_with_changing_script_request_ids():
    """
    T1: Changing dynamic JavaScript request IDs (e.g. CacheDetection.RequestID,
    page.requestId) must NOT alter extracted visible text or content hash.
    Repeated captures must produce identical normalized text and hash.
    """
    url_req1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?request_id=REQ-ALPHA-1111"
    url_req2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?request_id=REQ-BETA-9999"

    cap1 = capture_page(url_req1, is_fixture=True)
    cap2 = capture_page(url_req2, is_fixture=True)

    # Neither capture should contain script content or request IDs
    assert "CacheDetection" not in cap1.normalized_text
    assert "REQ-ALPHA-1111" not in cap1.normalized_text
    assert "CacheDetection" not in cap2.normalized_text
    assert "REQ-BETA-9999" not in cap2.normalized_text

    # Visible text and content hash must be completely identical
    assert cap1.normalized_text == cap2.normalized_text
    assert cap1.content_hash == cap2.content_hash

    # Must contain meaningful visible content
    assert "AcuTime Precision Chronometer 400" in cap1.normalized_text
    assert "$4999" in cap1.normalized_text
    assert "In Stock" in cap1.normalized_text


def test_identical_visible_content_with_changing_hidden_metadata():
    """
    T2: Changing hidden metadata (display:none elements, hidden attributes)
    must NOT alter extracted visible text or content hash.
    """
    url_meta1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?hidden_meta=SESSION-AAA-001"
    url_meta2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?hidden_meta=SESSION-ZZZ-999"

    cap1 = capture_page(url_meta1, is_fixture=True)
    cap2 = capture_page(url_meta2, is_fixture=True)

    assert "SESSION-AAA-001" not in cap1.normalized_text
    assert "SESSION-ZZZ-999" not in cap2.normalized_text
    assert cap1.normalized_text == cap2.normalized_text
    assert cap1.content_hash == cap2.content_hash


def test_product_price_changes_detected():
    """
    T3: Product price changes must produce differing normalized text and hashes,
    and a clear diff indicating price modification.
    """
    url_p1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999"
    url_p2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=3999"

    cap1 = capture_page(url_p1, is_fixture=True)
    cap2 = capture_page(url_p2, is_fixture=True)

    assert cap1.content_hash != cap2.content_hash
    assert "$4999" in cap1.normalized_text
    assert "$3999" in cap2.normalized_text

    # Verify structured text diff
    diff_blocks = compute_text_diff(cap1.normalized_text, cap2.normalized_text)
    removed = [b["text"] for b in diff_blocks if b["kind"] == "remove"]
    added = [b["text"] for b in diff_blocks if b["kind"] == "add"]

    assert any("$4999" in r for r in removed)
    assert any("$3999" in a for a in added)
    # The diff must NOT contain any script or telemetry additions/removals
    assert not any("CacheDetection" in str(b) for b in diff_blocks)
    assert not any("requestId" in str(b) for b in diff_blocks)


def test_stock_availability_changes_detected():
    """
    T4: Stock availability changes must produce distinct hashes and readable diffs.
    """
    url_stock1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?availability=In+Stock+(Ships+in+24+hours)"
    url_stock2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?availability=Currently+Unavailable"

    cap1 = capture_page(url_stock1, is_fixture=True)
    cap2 = capture_page(url_stock2, is_fixture=True)

    assert cap1.content_hash != cap2.content_hash
    assert "In Stock (Ships in 24 hours)" in cap1.normalized_text
    assert "Currently Unavailable" in cap2.normalized_text

    diff_blocks = compute_text_diff(cap1.normalized_text, cap2.normalized_text)
    assert any("In Stock" in b["text"] for b in diff_blocks if b["kind"] == "remove")
    assert any("Currently Unavailable" in b["text"] for b in diff_blocks if b["kind"] == "add")


def test_watch_selector_isolates_meaningful_text():
    """
    T5: WATCH selector isolates only the target element text, ignoring changes
    in other parts of the document.
    """
    mock_watch_rule = MagicMock()
    mock_watch_rule.rule_type = "watch"
    mock_watch_rule.css_selector = "#price"

    # Vary title and banner, keep price identical
    url1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&title=Title+One&banner=Banner+One"
    url2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=4999&title=Title+Two&banner=Banner+Two"

    cap1 = capture_page(url1, is_fixture=True, rules=[mock_watch_rule])
    cap2 = capture_page(url2, is_fixture=True, rules=[mock_watch_rule])

    # Only #price was watched
    assert cap1.normalized_text.strip() == "$4999"
    assert cap2.normalized_text.strip() == "$4999"
    assert cap1.content_hash == cap2.content_hash

    # Now change the watched price
    url3 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=7999&title=Title+Two"
    cap3 = capture_page(url3, is_fixture=True, rules=[mock_watch_rule])
    assert cap3.normalized_text.strip() == "$7999"
    assert cap3.content_hash != cap1.content_hash


def test_ignore_selector_covers_noisy_region():
    """
    T6: IGNORE selector covers a noisy region (e.g. #banner or #timestamp)
    so mutations within it produce unchanged content hash.
    """
    mock_ignore_rule = MagicMock()
    mock_ignore_rule.rule_type = "ignore"
    mock_ignore_rule.css_selector = "#banner"

    url1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?banner=Banner+A&timestamp=10:00:00"
    url2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?banner=Banner+B&timestamp=11:00:00"

    cap1 = capture_page(url1, is_fixture=True, rules=[mock_ignore_rule])
    cap2 = capture_page(url2, is_fixture=True, rules=[mock_ignore_rule])

    # #banner is completely omitted from both
    assert "Banner A" not in cap1.normalized_text
    assert "Banner B" not in cap2.normalized_text
    assert "System Clock:" not in cap1.normalized_text
    assert cap1.normalized_text == cap2.normalized_text
    assert cap1.content_hash == cap2.content_hash


# -----------------------------------------------------------------------------
# 2. End-to-End Checker Pipeline Tests (Safe Transition & Unchanged State)
# -----------------------------------------------------------------------------

def test_checker_pipeline_unchanged_on_script_request_id_change():
    """
    T7: In the full worker pipeline (execute_check), changing only dynamic script IDs
    produces CheckRunStateEnum.UNCHANGED and does not increment version count.
    """
    monitor_id = uuid.uuid4()
    check1_id = uuid.uuid4()
    check2_id = uuid.uuid4()

    url_v1 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?request_id=REQ-001"
    url_v2 = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?request_id=REQ-002"

    # Pre-calculate what clean visible text produces
    cap1 = capture_page(url_v1, is_fixture=True)

    mock_monitor = MagicMock(spec=Monitor)
    mock_monitor.id = monitor_id
    mock_monitor.url = url_v2
    mock_monitor.canonical_url = url_v2
    mock_monitor.rules = []
    mock_monitor.interval_minutes = 15
    mock_monitor.rebaseline_needed = False

    # Simulate existing version 1 in DB created from url_v1
    mock_v1 = MagicMock(spec=Version)
    mock_v1.id = uuid.uuid4()
    mock_v1.sequence_number = 1
    mock_v1.content_hash = cap1.content_hash
    mock_v1.normalized_text = cap1.normalized_text

    mock_check2 = MagicMock(spec=CheckRun)
    mock_check2.id = check2_id
    mock_check2.monitor_id = monitor_id
    mock_check2.state = CheckRunStateEnum.QUEUED
    mock_check2.attempt = 0

    mock_db = MagicMock()
    # Return check_run, monitor, locked_monitor, latest_version
    def query_router(model):
        query_mock = MagicMock()
        if model == CheckRun:
            query_mock.filter.return_value.first.return_value = mock_check2
        elif model == Monitor:
            query_mock.filter.return_value.first.return_value = mock_monitor
            query_mock.filter.return_value.with_for_update.return_value.first.return_value = mock_monitor
        elif model == Version:
            query_mock.filter.return_value.order_by.return_value.first.return_value = mock_v1
        return query_mock

    mock_db.query.side_effect = query_router

    with patch("app.services.checker.SessionLocal", return_value=mock_db), \
         patch("app.services.checker.shared_fetch_service.get_cached_fetch", return_value=None), \
         patch("app.services.checker.rate_limiter.acquire_domain_lock", return_value=True), \
         patch("app.services.checker.rate_limiter.release_domain_lock", return_value=True), \
         patch("app.services.checker.rate_limiter.get_domain_cooldown_remaining", return_value=0), \
         patch("app.services.checker.save_screenshot", return_value="dummy/path.png"):
        execute_check(check2_id)

    # The check state must be UNCHANGED
    assert mock_check2.state == CheckRunStateEnum.UNCHANGED
    # Content hash matches
    assert mock_check2.content_hash == cap1.content_hash
    # No new Version was added
    assert not mock_db.add.called


def test_checker_safe_transition_from_legacy_script_polluted_baseline():
    """
    T8: When an existing monitor in DB has a legacy baseline version polluted with
    raw JavaScript (e.g. from pre-fix capture of Amazon India), the next check
    safely transitions to a clean visible text BASELINE without triggering false alerts.
    """
    monitor_id = uuid.uuid4()
    check_id = uuid.uuid4()
    url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"

    # Simulate legacy version with raw script noise in normalized_text
    legacy_polluted_text = (
        "AcuTime Precision Chronometer 400\n"
        "$4999\n"
        "window.CacheDetection = { RequestID: \"OLD-REQ-000\" };\n"
        "var page = { requestId: \"OLD-REQ-000\" };"
    )

    mock_monitor = MagicMock(spec=Monitor)
    mock_monitor.id = monitor_id
    mock_monitor.url = url
    mock_monitor.canonical_url = url
    mock_monitor.rules = []
    mock_monitor.interval_minutes = 15
    mock_monitor.rebaseline_needed = False  # Not explicitly set by user

    mock_v1 = MagicMock(spec=Version)
    mock_v1.id = uuid.uuid4()
    mock_v1.sequence_number = 1
    mock_v1.content_hash = "legacy_polluted_hash_12345"
    mock_v1.normalized_text = legacy_polluted_text

    mock_check = MagicMock(spec=CheckRun)
    mock_check.id = check_id
    mock_check.monitor_id = monitor_id
    mock_check.state = CheckRunStateEnum.QUEUED
    mock_check.attempt = 0

    mock_db = MagicMock()
    def query_router(model):
        query_mock = MagicMock()
        if model == CheckRun:
            query_mock.filter.return_value.first.return_value = mock_check
        elif model == Monitor:
            query_mock.filter.return_value.first.return_value = mock_monitor
            query_mock.filter.return_value.with_for_update.return_value.first.return_value = mock_monitor
        elif model == Version:
            query_mock.filter.return_value.order_by.return_value.first.return_value = mock_v1
        return query_mock

    mock_db.query.side_effect = query_router

    with patch("app.services.checker.SessionLocal", return_value=mock_db), \
         patch("app.services.checker.shared_fetch_service.get_cached_fetch", return_value=None), \
         patch("app.services.checker.rate_limiter.acquire_domain_lock", return_value=True), \
         patch("app.services.checker.rate_limiter.release_domain_lock", return_value=True), \
         patch("app.services.checker.rate_limiter.get_domain_cooldown_remaining", return_value=0), \
         patch("app.services.checker.save_screenshot", return_value="dummy/path.png"):
        execute_check(check_id)

    # Must transition safely to BASELINE (not CHANGED)
    assert mock_check.state == CheckRunStateEnum.BASELINE
    assert mock_db.add.called
    added_versions = [arg[0][0] for arg in mock_db.add.call_args_list if isinstance(arg[0][0], Version)]
    assert len(added_versions) > 0
    added_version = added_versions[0]
    # Clean text in the new baseline version
    assert "CacheDetection" not in added_version.normalized_text
    assert "requestId" not in added_version.normalized_text
    assert "$4999" in added_version.normalized_text
    assert added_version.sequence_number == 2
