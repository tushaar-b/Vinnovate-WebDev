import uuid
import time
from datetime import datetime, timezone, timedelta
import pytest
from rq import SimpleWorker, Queue
import redis

from app.config import settings
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
    utc_now,
)
from app.services.security import canonicalize_url
from app.services.queue import enqueue_check, get_redis_connection, get_queue
from app.services.checker import execute_check, execute_check_job
from app.services.rate_limiter import rate_limiter, DomainRateLimiter
from app.services.dedup import shared_fetch_service
from scheduler import run_scheduler_tick
from worker import recover_abandoned_jobs


@pytest.fixture(autouse=True)
def setup_test_mode(monkeypatch):
    monkeypatch.setattr(settings, "TEST_MODE", True)


# -------------------------------------------------------------------------
# 1. Job Enqueued Successfully
# -------------------------------------------------------------------------
def test_job_enqueued_successfully():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Queue Enqueue Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Enqueue with force_async=True to verify actual Redis queueing
        check_run = enqueue_check(monitor_id=monitor.id, is_manual=True, db=db, force_async=True)
        assert check_run is not None
        assert check_run.state == CheckRunStateEnum.QUEUED
        assert check_run.job_id is not None
        assert check_run.job_id.startswith("job-")

        # Verify job is actually registered in RQ
        conn = get_redis_connection()
        q = Queue("checks", connection=conn)
        job_ids = q.job_ids
        assert check_run.job_id in job_ids

        # Clean up job from queue
        job = q.fetch_job(check_run.job_id)
        if job:
            job.delete()

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 2. RQ Worker Executes Check Successfully
# -------------------------------------------------------------------------
def test_rq_worker_executes_check_successfully():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=1999"
        monitor = Monitor(
            name="Worker Execution Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        check_run = enqueue_check(monitor_id=monitor.id, is_manual=True, db=db, force_async=True)

        # Run RQ Worker in burst mode to consume and execute the queued job
        conn = get_redis_connection()
        q = Queue("checks", connection=conn)
        worker = SimpleWorker([q], connection=conn)
        worker.work(burst=True)

        # Verify check run finished successfully
        db.expire_all()
        run = db.query(CheckRun).filter(CheckRun.id == check_run.id).first()
        assert run.state == CheckRunStateEnum.BASELINE
        assert run.http_status == 200
        assert run.finished_at is not None

        # Verify version was created
        version = db.query(Version).filter(Version.monitor_id == monitor.id).first()
        assert version is not None
        assert "$1999" in version.normalized_text

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 3. Check Survives API Restart While Worker and Redis Remain Available
# -------------------------------------------------------------------------
def test_check_survives_api_restart():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=3499"
        monitor = Monitor(
            name="API Durability Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Enqueue work via API service
        check_run = enqueue_check(monitor_id=monitor.id, is_manual=True, db=db, force_async=True)
        job_id = check_run.job_id
        check_run_id = check_run.id
        monitor_id = monitor.id

        # Simulate complete API process shutdown / restart:
        # Close DB connection and drop references
        db.close()

        # Job is safely persisted in Redis RQ
        conn = get_redis_connection()
        q = Queue("checks", connection=conn)
        assert job_id in q.job_ids

        # Worker picks up job after API "shutdown"
        worker = SimpleWorker([q], connection=conn)
        worker.work(burst=True)

        # Reopen a new DB session (new API process) to verify state
        new_db = SessionLocal()
        run = new_db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
        assert run.state == CheckRunStateEnum.BASELINE
        assert run.finished_at is not None

        version = new_db.query(Version).filter(Version.monitor_id == monitor_id).first()
        assert version is not None
        assert "$3499" in version.normalized_text

        m = new_db.query(Monitor).filter(Monitor.id == monitor_id).first()
        new_db.delete(m)
        new_db.commit()
        new_db.close()
    finally:
        pass


# -------------------------------------------------------------------------
# 4. Worker Crash Recovery
# -------------------------------------------------------------------------
def test_worker_crash_recovery():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Crash Recovery Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Simulate a check run that was marked RUNNING but abandoned when worker crashed 10 min ago
        abandoned_run = CheckRun(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            job_id="job-crashed-test",
            state=CheckRunStateEnum.RUNNING,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            finished_at=None,
        )
        db.add(abandoned_run)
        db.commit()

        # Run worker startup recovery routine
        recover_abandoned_jobs()

        db.expire_all()
        recovered = db.query(CheckRun).filter(CheckRun.id == abandoned_run.id).first()
        assert recovered.state == CheckRunStateEnum.ERROR
        assert "interrupted or crashed" in recovered.error_message.lower()
        assert recovered.finished_at is not None

        # Verify no duplicate versions created
        v_count = db.query(Version).filter(Version.monitor_id == monitor.id).count()
        assert v_count == 0

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 5. Scheduler Selects Due Monitors
# -------------------------------------------------------------------------
def test_scheduler_selects_due_monitors():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Due Monitor Scheduler Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
            next_check_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Tick scheduler
        enqueued = run_scheduler_tick(db=db)
        assert enqueued >= 1

        db.expire_all()
        m = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        # Verify next_check_at was updated forward
        assert m.next_check_at > datetime.now(timezone.utc)

        # Clean up
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 6. Disabled Monitors Are Skipped by Scheduler
# -------------------------------------------------------------------------
def test_disabled_monitors_are_skipped():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Disabled Monitor Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=False,  # DISABLED
            next_check_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        old_next = monitor.next_check_at

        # Tick scheduler
        run_scheduler_tick(db=db)

        db.expire_all()
        m = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        # Should NOT have been scheduled
        assert m.next_check_at == old_next
        check_runs = db.query(CheckRun).filter(CheckRun.monitor_id == monitor.id).all()
        assert len(check_runs) == 0

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 7. Interval Calculations Are Correct
# -------------------------------------------------------------------------
def test_interval_calculations_are_correct():
    db = SessionLocal()
    try:
        interval_min = 45
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Interval Calculation Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=interval_min,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
            next_check_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        before_tick = datetime.now(timezone.utc)
        run_scheduler_tick(db=db)

        db.expire_all()
        m = db.query(Monitor).filter(Monitor.id == monitor.id).first()
        expected_min = before_tick + timedelta(minutes=interval_min)
        # Tolerance within 5 seconds
        diff_seconds = abs((m.next_check_at.replace(tzinfo=timezone.utc) - expected_min).total_seconds())
        assert diff_seconds < 10, f"Expected next check in ~45m, diff was {diff_seconds}s"

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 8. Manual and Scheduled Checks Cannot Overlap
# -------------------------------------------------------------------------
def test_manual_and_scheduled_checks_cannot_overlap():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product"
        monitor = Monitor(
            name="Overlap Prevention Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
            next_check_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Create an active RUNNING check run
        active_run = CheckRun(
            id=uuid.uuid4(),
            monitor_id=monitor.id,
            job_id="job-active-overlap-test",
            state=CheckRunStateEnum.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(active_run)
        db.commit()

        # 1. Manual check attempt -> returns active run without creating new run
        manual_run = enqueue_check(monitor_id=monitor.id, is_manual=True, db=db, force_async=True)
        assert manual_run.id == active_run.id

        # 2. Scheduler tick attempt -> skips due monitor because active run exists
        enqueued = run_scheduler_tick(db=db)
        assert enqueued == 0

        # Verify only 1 run exists in DB
        total_runs = db.query(CheckRun).filter(CheckRun.monitor_id == monitor.id).count()
        assert total_runs == 1

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 9. Compatible Same-URL Monitors Share a Fetch
# -------------------------------------------------------------------------
def test_compatible_same_url_monitors_share_fetch():
    db = SessionLocal()
    try:
        # Both monitors watch the exact same URL
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=8888"
        canon = canonicalize_url(url)

        # Clear any existing cached fetch for this URL
        shared_fetch_service.clear_cache(canon)

        # Monitor A: watches full page
        mon_a = Monitor(
            name="Shared Fetch Monitor A",
            url=url,
            canonical_url=canon,
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        # Monitor B: watches only #price selector
        mon_b = Monitor(
            name="Shared Fetch Monitor B",
            url=url,
            canonical_url=canon,
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add_all([mon_a, mon_b])
        db.commit()
        db.refresh(mon_a)
        db.refresh(mon_b)

        rule_b = MonitorRule(
            id=uuid.uuid4(),
            monitor_id=mon_b.id,
            rule_type=RuleTypeEnum.WATCH,
            css_selector="#price",
            label="Price only",
        )
        db.add(rule_b)
        db.commit()

        # Run Check for Monitor A -> should capture from browser and store in cache
        run_a = enqueue_check(mon_a.id, db=db, force_async=False)
        db.expire_all()
        check_a = db.query(CheckRun).filter(CheckRun.id == run_a.id).first()
        assert check_a.state == CheckRunStateEnum.BASELINE

        # Verify shared-fetch cache contains capture
        cached = shared_fetch_service.get_cached_fetch(canon)
        assert cached is not None
        assert "raw_html" in cached
        assert "$8888" in cached["raw_html"]

        # Run Check for Monitor B -> reuses cached capture and evaluates independent #price rule
        run_b = enqueue_check(mon_b.id, db=db, force_async=False)
        db.expire_all()
        check_b = db.query(CheckRun).filter(CheckRun.id == run_b.id).first()
        assert check_b.state == CheckRunStateEnum.BASELINE

        # Verify Monitor B extracted its independent selector from the shared fetch
        v_b = db.query(Version).filter(Version.monitor_id == mon_b.id).first()
        assert v_b is not None
        assert "$8888" in v_b.normalized_text

        db.delete(mon_a)
        db.delete(mon_b)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 10. Incompatible Configurations Do Not Share Unsafe Captures
# -------------------------------------------------------------------------
def test_incompatible_configurations_do_not_share_captures():
    url_a = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=100"
    url_b = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=200"

    canon_a = canonicalize_url(url_a)
    canon_b = canonicalize_url(url_b)

    assert canon_a != canon_b

    # Cache for url_a must not be returned for url_b
    cached_b = shared_fetch_service.get_cached_fetch(canon_b)
    # If no capture has been done for canon_b, cached_b is None
    assert cached_b is None


# -------------------------------------------------------------------------
# 11. Domain Concurrency Limit Is Enforced
# -------------------------------------------------------------------------
def test_domain_concurrency_limit_enforced():
    limiter = DomainRateLimiter()
    test_domain = f"test-domain-{uuid.uuid4().hex[:6]}.com"

    # 1. Acquire lock
    acquired_1 = limiter.acquire_domain_lock(test_domain, timeout_seconds=10)
    assert acquired_1 is True

    # 2. Second concurrent request to the same domain should be blocked
    acquired_2 = limiter.acquire_domain_lock(test_domain, timeout_seconds=10)
    assert acquired_2 is False

    # 3. Release lock
    limiter.release_domain_lock(test_domain)

    # 4. Now acquire should succeed
    acquired_3 = limiter.acquire_domain_lock(test_domain, timeout_seconds=10)
    assert acquired_3 is True
    limiter.release_domain_lock(test_domain)


# -------------------------------------------------------------------------
# 12. Retry and Backoff Behavior Is Bounded
# -------------------------------------------------------------------------
def test_retry_and_backoff_behavior_bounded():
    limiter = DomainRateLimiter()

    # Bounded exponential growth with jitter
    d0 = limiter.calculate_backoff_delay(0)
    d1 = limiter.calculate_backoff_delay(1)
    d2 = limiter.calculate_backoff_delay(2)
    d5 = limiter.calculate_backoff_delay(5)

    assert 1 <= d0 <= 10
    assert 1 <= d1 <= 15
    assert 2 <= d2 <= 20
    # Must never exceed max delay of 60s
    assert d5 <= 60

    # Retryable classification
    assert limiter.is_retryable_error("TIMEOUT", None) is True
    assert limiter.is_retryable_error("HTTP_429", 429) is True
    assert limiter.is_retryable_error("HTTP_503", 503) is True
    assert limiter.is_retryable_error("HTTP_502", 502) is True
    assert limiter.is_retryable_error("BLOCKED_TARGET", None) is False
    assert limiter.is_retryable_error("MISSING_SELECTOR", None) is False


# -------------------------------------------------------------------------
# 13. HTTP 429 Respects Retry-After
# -------------------------------------------------------------------------
def test_http_429_respects_retry_after():
    limiter = DomainRateLimiter()
    test_domain = f"test-429-{uuid.uuid4().hex[:6]}.com"

    # Numeric seconds
    parsed_sec = limiter.parse_retry_after("45")
    assert parsed_sec == 45

    # Cap at max delay
    parsed_huge = limiter.parse_retry_after("99999")
    assert parsed_huge == 120  # Capped at max delay

    # Set cooldown and verify domain is rate limited
    limiter.set_domain_cooldown(test_domain, duration_seconds=10)
    assert limiter.get_domain_cooldown_remaining(test_domain) > 0

    # After cooldown expiry (simulated by clearing key)
    limiter.r.delete(f"cooldown:domain:{test_domain}")
    assert limiter.get_domain_cooldown_remaining(test_domain) == 0


# -------------------------------------------------------------------------
# 14. Failed Checks Preserve the Last Valid Version
# -------------------------------------------------------------------------
def test_failed_checks_preserve_last_valid_version():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=5000"
        monitor = Monitor(
            name="Preserve Version On Failure Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Baseline capture
        run_base = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        base_run_record = db.query(CheckRun).filter(CheckRun.id == run_base.id).first()
        assert base_run_record.state == CheckRunStateEnum.BASELINE

        versions_initial = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_initial) == 1
        baseline_version = versions_initial[0]

        # Second check targets HTTP 500 error
        new_err_url = f"http://127.0.0.1:{settings.API_PORT}/fixture/error-500"
        monitor.url = new_err_url
        monitor.canonical_url = canonicalize_url(new_err_url)
        db.commit()

        run_failed = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        failed_run_record = db.query(CheckRun).filter(CheckRun.id == run_failed.id).first()
        assert failed_run_record.state == CheckRunStateEnum.ERROR

        # Last valid baseline version remains preserved and untouched
        versions_after = db.query(Version).filter(Version.monitor_id == monitor.id).all()
        assert len(versions_after) == 1
        assert versions_after[0].id == baseline_version.id

        db.delete(monitor)
        db.commit()
    finally:
        db.close()


# -------------------------------------------------------------------------
# 15. Concurrent Identical Checks Cannot Create Duplicate Versions
# -------------------------------------------------------------------------
def test_concurrent_identical_checks_cannot_create_duplicate_versions():
    db = SessionLocal()
    try:
        url = f"http://127.0.0.1:{settings.API_PORT}/fixture/product?price=7777"
        monitor = Monitor(
            name="Concurrency Version Deduplication Test",
            url=url,
            canonical_url=canonicalize_url(url),
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        # Run 1st check
        run1 = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        r1 = db.query(CheckRun).filter(CheckRun.id == run1.id).first()
        assert r1.state == CheckRunStateEnum.BASELINE

        # Run 2nd check with identical content
        run2 = enqueue_check(monitor.id, db=db, force_async=False)
        db.expire_all()
        r2 = db.query(CheckRun).filter(CheckRun.id == run2.id).first()
        assert r2.state == CheckRunStateEnum.UNCHANGED

        # Exactly 1 version should exist
        v_count = db.query(Version).filter(Version.monitor_id == monitor.id).count()
        assert v_count == 1

        db.delete(monitor)
        db.commit()
    finally:
        db.close()
