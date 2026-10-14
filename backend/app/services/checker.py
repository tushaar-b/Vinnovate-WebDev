import uuid
import time
from datetime import timedelta
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import (
    Monitor,
    CheckRun,
    Version,
    CheckRunStateEnum,
    MonitorStatusEnum,
    utc_now,
)
from app.services.browser import capture_page, BrowserCaptureError, CaptureResult
from app.services.security import SecurityValidationError
from app.services.storage import save_screenshot
from app.services.rate_limiter import rate_limiter, get_domain_from_url
from app.services.dedup import shared_fetch_service
from app.database import SessionLocal


def execute_check_job(check_run_id_val: str | uuid.UUID) -> None:
    """
    RQ worker entry point for processing a queued check run.
    """
    if isinstance(check_run_id_val, str):
        check_run_id = uuid.UUID(check_run_id_val)
    else:
        check_run_id = check_run_id_val
    execute_check(check_run_id)


def execute_check(check_run_id: uuid.UUID) -> None:
    """
    Executes a queued check run in the worker pipeline:
    1. Fetches check run and associated monitor.
    2. Enforces per-domain concurrency lock and cooldown.
    3. Leverages shared-fetch coalescing for identical canonical URLs.
    4. Handles safe baseline transition when monitor rules change (extraction scope revision).
    5. Persists results, version (if baseline, safe transition, or changed), and screenshot artifact.
    6. Implements bounded exponential backoff on retryable failures.
    7. Handles non-retryable errors cleanly, preserving baseline version on failure.
    """
    db: Session = SessionLocal()
    domain = ""
    domain_locked = False

    try:
        check_run = db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
        if not check_run:
            return

        # Idempotency check: if job has already reached terminal status, skip
        if check_run.state not in (CheckRunStateEnum.QUEUED, CheckRunStateEnum.RUNNING):
            return

        monitor = db.query(Monitor).filter(Monitor.id == check_run.monitor_id).first()
        if not monitor:
            check_run.state = CheckRunStateEnum.ERROR
            check_run.error_message = "Associated monitor not found."
            check_run.finished_at = utc_now()
            db.commit()
            return

        # Mark check run as running
        check_run.state = CheckRunStateEnum.RUNNING
        check_run.started_at = utc_now()
        check_run.attempt += 1
        db.commit()

        # Domain Rate Limiting & Concurrency Controls
        domain = get_domain_from_url(monitor.url)
        cooldown = rate_limiter.get_domain_cooldown_remaining(domain)
        if cooldown > 0 and not settings.TEST_MODE:
            # Respect domain cooldown spacing
            time.sleep(min(cooldown, 5))

        domain_locked = rate_limiter.acquire_domain_lock(domain)

        # Check Shared-Fetch Coalescing Cache
        cached_fetch = shared_fetch_service.get_cached_fetch(monitor.canonical_url)
        is_shared_fetch = False
        result: Optional[CaptureResult] = None

        if cached_fetch is not None:
            # Reusing captured page DOM and screenshot from identical canonical URL
            try:
                raw_text, normalized_text, content_hash = shared_fetch_service.evaluate_monitor_rules_on_dom(
                    raw_html=cached_fetch["raw_html"],
                    rules=monitor.rules,
                )
                result = CaptureResult(
                    title=cached_fetch["title"],
                    final_url=cached_fetch["final_url"],
                    visible_text=raw_text,
                    normalized_text=normalized_text,
                    content_hash=content_hash,
                    screenshot_bytes=cached_fetch["screenshot_bytes"],
                    http_status=cached_fetch["http_status"],
                    duration_ms=cached_fetch["duration_ms"],
                    elements=cached_fetch.get("elements"),
                    raw_html=cached_fetch["raw_html"],
                )
                is_shared_fetch = True
            except BrowserCaptureError:
                # If cached evaluation raised error (e.g. missing selector), re-raise to handle properly
                raise
            except Exception:
                # Fallback to direct capture if cache parsing fails
                result = None

        if result is None:
            # Execute browser capture
            is_fixture = "/fixture" in monitor.url
            result = capture_page(monitor.url, is_fixture=is_fixture, rules=monitor.rules)

            # Store in shared-fetch cache for subsequent compatible monitors
            if result.raw_html:
                shared_fetch_service.store_cached_fetch(
                    canonical_url=monitor.canonical_url,
                    result=result,
                    raw_html=result.raw_html,
                )

        # Handle HTTP 429 Too Many Requests
        if result.http_status == 429:
            raise BrowserCaptureError("Target returned HTTP 429 Too Many Requests.", error_code="HTTP_429", http_status=429)

        # Atomically lock monitor row to serialize version creation and sequence numbering
        locked_monitor = (
            db.query(Monitor)
            .filter(Monitor.id == monitor.id)
            .with_for_update()
            .first()
        )

        latest_version = (
            db.query(Version)
            .filter(Version.monitor_id == monitor.id)
            .order_by(Version.sequence_number.desc())
            .first()
        )

        # Safe Baseline Transition:
        # When extraction scope or rules were revised, transition the baseline without classifying as website change
        is_safe_rebaseline = bool(locked_monitor.rebaseline_needed)

        if latest_version is None or is_safe_rebaseline:
            # FIRST CHECK OR SAFE REBASELINE TRANSITION
            next_seq = 1 if latest_version is None else (latest_version.sequence_number + 1)
            new_version_id = uuid.uuid4()
            screenshot_rel_path = save_screenshot(
                monitor.id, new_version_id, result.screenshot_bytes
            )

            version = Version(
                id=new_version_id,
                monitor_id=monitor.id,
                check_run_id=check_run.id,
                sequence_number=next_seq,
                content_hash=result.content_hash,
                normalized_text=result.normalized_text,
                screenshot_path=screenshot_rel_path,
                captured_at=utc_now(),
                stable_alert_count=0,
            )
            db.add(version)

            check_run.state = CheckRunStateEnum.BASELINE
            check_run.content_hash = result.content_hash
            check_run.http_status = result.http_status
            check_run.duration_ms = result.duration_ms
            check_run.finished_at = utc_now()

            locked_monitor.status = MonitorStatusEnum.OK
            locked_monitor.rebaseline_needed = False
            locked_monitor.last_checked_at = utc_now()
            locked_monitor.last_changed_at = utc_now()
            locked_monitor.next_check_at = utc_now() + timedelta(minutes=locked_monitor.interval_minutes)
            locked_monitor.last_error = None
            db.commit()

        elif latest_version.content_hash == result.content_hash:
            # UNCHANGED: Content hash matches previous version
            check_run.state = CheckRunStateEnum.UNCHANGED
            check_run.content_hash = result.content_hash
            check_run.http_status = result.http_status
            check_run.duration_ms = result.duration_ms
            check_run.finished_at = utc_now()

            locked_monitor.status = MonitorStatusEnum.OK
            locked_monitor.last_checked_at = utc_now()
            locked_monitor.next_check_at = utc_now() + timedelta(minutes=locked_monitor.interval_minutes)
            locked_monitor.last_error = None
            db.commit()

        else:
            # CHANGED: Content hash differs from previous version
            new_version_id = uuid.uuid4()
            screenshot_rel_path = save_screenshot(
                monitor.id, new_version_id, result.screenshot_bytes
            )

            version = Version(
                id=new_version_id,
                monitor_id=monitor.id,
                check_run_id=check_run.id,
                sequence_number=latest_version.sequence_number + 1,
                content_hash=result.content_hash,
                normalized_text=result.normalized_text,
                screenshot_path=screenshot_rel_path,
                captured_at=utc_now(),
                stable_alert_count=0,
            )
            db.add(version)

            check_run.state = CheckRunStateEnum.CHANGED
            check_run.content_hash = result.content_hash
            check_run.http_status = result.http_status
            check_run.duration_ms = result.duration_ms
            check_run.finished_at = utc_now()

            locked_monitor.status = MonitorStatusEnum.CHANGED
            locked_monitor.last_checked_at = utc_now()
            locked_monitor.last_changed_at = utc_now()
            locked_monitor.next_check_at = utc_now() + timedelta(minutes=locked_monitor.interval_minutes)
            locked_monitor.last_error = None

            # Generate change summary for alerts
            prev_t = latest_version.normalized_text.strip() if latest_version else ""
            new_t = result.normalized_text.strip()
            if prev_t == new_t:
                summary = "Visual presentation or layout changed."
            elif len(prev_t) < 80 and len(new_t) < 80:
                summary = f"Changed from '{prev_t}' to '{new_t}'"
            else:
                summary = f"Content updated ({len(new_t)} chars, previous {len(prev_t)} chars)."

            db.commit()

            # Enqueue notification outbox entries for confirmed CHANGED result
            from app.services.notifier import create_outbox_entries_for_changed_version
            create_outbox_entries_for_changed_version(
                db=db,
                monitor=locked_monitor,
                version=version,
                change_summary=summary,
            )

    except SecurityValidationError as e:
        check_run.state = CheckRunStateEnum.BLOCKED
        check_run.error_code = e.code
        check_run.error_message = e.message
        check_run.finished_at = utc_now()

        monitor.status = MonitorStatusEnum.BLOCKED
        monitor.last_error = e.message
        monitor.last_checked_at = utc_now()
        monitor.next_check_at = utc_now() + timedelta(minutes=monitor.interval_minutes)
        db.commit()

    except BrowserCaptureError as e:
        # Check if error is retryable
        retryable = rate_limiter.is_retryable_error(e.error_code, e.http_status)
        if retryable and check_run.attempt < 2 and not settings.TEST_MODE:
            # Re-enqueue with bounded exponential backoff
            delay = rate_limiter.calculate_backoff_delay(check_run.attempt)
            check_run.state = CheckRunStateEnum.QUEUED
            check_run.error_message = f"Transient failure, retrying: {e.message}"
            db.commit()
            from app.services.queue import get_queue
            q = get_queue("checks")
            q.enqueue_in(
                timedelta(seconds=delay),
                "app.services.checker.execute_check_job",
                str(check_run.id),
            )
            return

        check_run.state = CheckRunStateEnum.BLOCKED if e.error_code == "BLOCKED" else CheckRunStateEnum.ERROR
        check_run.error_code = e.error_code
        check_run.error_message = e.message
        check_run.http_status = e.http_status
        check_run.finished_at = utc_now()

        monitor.status = MonitorStatusEnum.BLOCKED if e.error_code == "BLOCKED" else MonitorStatusEnum.ERROR
        monitor.last_error = e.message
        monitor.last_checked_at = utc_now()
        monitor.next_check_at = utc_now() + timedelta(minutes=monitor.interval_minutes)
        db.commit()

    except Exception as e:
        check_run.state = CheckRunStateEnum.ERROR
        check_run.error_code = "UNEXPECTED_ERROR"
        check_run.error_message = str(e)
        check_run.finished_at = utc_now()

        monitor.status = MonitorStatusEnum.ERROR
        monitor.last_error = str(e)
        monitor.last_checked_at = utc_now()
        monitor.next_check_at = utc_now() + timedelta(minutes=monitor.interval_minutes)
        db.commit()

    finally:
        # Always release domain lock and establish cooldown
        if domain and domain_locked:
            rate_limiter.release_domain_lock(domain)
            rate_limiter.set_domain_cooldown(domain)
        db.close()
