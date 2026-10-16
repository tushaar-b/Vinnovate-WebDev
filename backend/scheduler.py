import logging
import time
from datetime import datetime, timezone, timedelta
import redis
from sqlalchemy import select, and_, or_

from app.config import settings
from app.database import SessionLocal
from app.models.models import Monitor, CheckRun, CheckRunStateEnum
from app.services.queue import enqueue_check
from app.services.judge import cleanup_expired_judge_monitors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("scheduler")


def run_scheduler_tick(db=None, redis_conn=None) -> int:
    """
    Executes a single scheduler tick.
    Returns the number of monitors enqueued.
    Can be called deterministically by test fixtures.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    if redis_conn is None:
        redis_conn = redis.from_url(settings.REDIS_URL)

    # Distributed lock for scheduler tick coordination
    lock = redis_conn.lock("lock:scheduler:tick", timeout=15, blocking_timeout=1)
    if not lock.acquire(blocking=False):
        logger.debug("Another scheduler instance holds the tick lock. Skipping tick.")
        if close_db:
            db.close()
        return 0

    enqueued_count = 0
    try:
        now = datetime.now(timezone.utc)

        # Automatic cleanup and disabling of expired judge evaluation monitors
        try:
            cleaned = cleanup_expired_judge_monitors(db)
            if cleaned > 0:
                logger.info(f"Cleaned up and disabled {cleaned} expired judge monitor(s)")
        except Exception as e:
            logger.warning(f"Error during expired judge monitor cleanup: {e}")

        # Select enabled monitors that are due and not expired, with SKIP LOCKED for concurrency safety
        due_monitors = (
            db.query(Monitor)
            .filter(
                and_(
                    Monitor.enabled.is_(True),
                    Monitor.next_check_at.isnot(None),
                    Monitor.next_check_at <= now,
                    or_(Monitor.expires_at.is_(None), Monitor.expires_at > now),
                )
            )
            .with_for_update(skip_locked=True)
            .all()
        )

        for monitor in due_monitors:
            # Check if there is already an active run (overlap prevention)
            active_run = (
                db.query(CheckRun)
                .filter(
                    CheckRun.monitor_id == monitor.id,
                    CheckRun.state.in_([CheckRunStateEnum.QUEUED, CheckRunStateEnum.RUNNING])
                )
                .first()
            )

            if active_run:
                logger.info(
                    f"Monitor {monitor.id} ({monitor.name}) is due but already has an active run ({active_run.id}). Skipping to prevent overlap."
                )
                # Postpone next_check_at slightly so it doesn't query-thrash
                monitor.next_check_at = now + timedelta(minutes=1)
                db.commit()
                continue

            # Update next_check_at based on monitor's interval
            # Handles downtime by scheduling the next interval cleanly from now
            interval = monitor.interval_minutes or 15
            monitor.next_check_at = now + timedelta(minutes=interval)
            db.commit()

            # Enqueue the check asynchronously to RQ queue
            enqueue_check(
                monitor_id=monitor.id,
                is_manual=False,
                db=db,
                redis_conn=redis_conn,
                force_async=True,
            )
            enqueued_count += 1
            logger.info(f"Enqueued scheduled check for monitor {monitor.id} ({monitor.name}), next at {monitor.next_check_at}")

    except Exception as e:
        logger.error(f"Error in scheduler tick: {e}", exc_info=True)
        db.rollback()
    finally:
        try:
            lock.release()
        except Exception:
            pass
        if close_db:
            db.close()

    return enqueued_count


def start_scheduler(tick_interval_seconds: int = 5):
    logger.info(f"Starting automatic scheduler (tick interval = {tick_interval_seconds}s)...")
    redis_conn = redis.from_url(settings.REDIS_URL)

    while True:
        try:
            run_scheduler_tick(redis_conn=redis_conn)
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}", exc_info=True)
        time.sleep(tick_interval_seconds)


if __name__ == "__main__":
    start_scheduler()
