import uuid
from datetime import timedelta
from sqlalchemy.orm import Session
from app.models.models import (
    Monitor,
    CheckRun,
    Version,
    CheckRunStateEnum,
    MonitorStatusEnum,
    utc_now,
)
from app.services.browser import capture_page, BrowserCaptureError
from app.services.security import SecurityValidationError
from app.services.storage import save_screenshot
from app.database import SessionLocal


def execute_check(check_run_id: uuid.UUID) -> None:
    """
    Executes a queued check run in the background:
    1. Fetches check run and associated monitor.
    2. Runs secure Playwright capture.
    3. Persists results, version (if baseline or changed), and screenshot artifact.
    4. Handles errors cleanly, preserving baseline version on failure.
    """
    db: Session = SessionLocal()
    try:
        check_run = db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
        if not check_run:
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

        # Execute browser capture with monitor rules applied
        is_fixture = "/fixture" in monitor.url
        try:
            result = capture_page(monitor.url, is_fixture=is_fixture, rules=monitor.rules)


            # Atomically lock monitor row to serialize version creation and sequence numbering
            # This guarantees concurrent checks cannot create duplicate sequence numbers or duplicate versions
            locked_monitor = (
                db.query(Monitor)
                .filter(Monitor.id == monitor.id)
                .with_for_update()
                .first()
            )

            # Query existing latest version for this monitor within locked transaction
            latest_version = (
                db.query(Version)
                .filter(Version.monitor_id == monitor.id)
                .order_by(Version.sequence_number.desc())
                .first()
            )


            if latest_version is None:
                # FIRST SUCCESSFUL CHECK: Create baseline version
                new_version_id = uuid.uuid4()
                screenshot_rel_path = save_screenshot(
                    monitor.id, new_version_id, result.screenshot_bytes
                )

                version = Version(
                    id=new_version_id,
                    monitor_id=monitor.id,
                    check_run_id=check_run.id,
                    sequence_number=1,
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

                monitor.status = MonitorStatusEnum.OK
                monitor.last_checked_at = utc_now()
                monitor.last_changed_at = utc_now()
                monitor.next_check_at = utc_now() + timedelta(minutes=monitor.interval_minutes)
                monitor.last_error = None

            elif latest_version.content_hash == result.content_hash:
                # UNCHANGED: Content hash matches previous version
                check_run.state = CheckRunStateEnum.UNCHANGED
                check_run.content_hash = result.content_hash
                check_run.http_status = result.http_status
                check_run.duration_ms = result.duration_ms
                check_run.finished_at = utc_now()

                monitor.status = MonitorStatusEnum.OK
                monitor.last_checked_at = utc_now()
                monitor.next_check_at = utc_now() + timedelta(minutes=monitor.interval_minutes)
                monitor.last_error = None

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

                monitor.status = MonitorStatusEnum.CHANGED
                monitor.last_checked_at = utc_now()
                monitor.last_changed_at = utc_now()
                monitor.next_check_at = utc_now() + timedelta(minutes=monitor.interval_minutes)
                monitor.last_error = None

            db.commit()

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
        db.close()
