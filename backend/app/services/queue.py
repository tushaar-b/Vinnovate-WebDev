import uuid
import redis
from typing import Optional
from rq import Queue
from rq.job import Job
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.models import Monitor, CheckRun, CheckRunStateEnum, utc_now


_rq_queue: Optional[Queue] = None
_redis_raw_conn: Optional[redis.Redis] = None


def get_redis_connection() -> redis.Redis:
    """Returns a Redis connection instance configured for RQ."""
    global _redis_raw_conn
    if _redis_raw_conn is None:
        _redis_raw_conn = redis.Redis.from_url(settings.REDIS_URL)
    return _redis_raw_conn


def get_queue(name: str = "checks", is_async: Optional[bool] = None) -> Queue:
    """Returns the RQ Queue for monitoring checks."""
    conn = get_redis_connection()
    if is_async is None:
        is_async = not getattr(settings, "TEST_MODE", False)
    return Queue(name, connection=conn, default_timeout=60, is_async=is_async)


def enqueue_check(
    monitor_id: uuid.UUID,
    is_manual: bool = False,
    db: Optional[Session] = None,
    redis_conn: Optional[redis.Redis] = None,
    force_async: Optional[bool] = None,
) -> CheckRun:
    """
    Durable check enqueueing pipeline:
    1. Prevents overlapping checks: checks if monitor already has a QUEUED or RUNNING check run.
    2. Atomically records CheckRun with unique job_id in PostgreSQL.
    3. Enqueues job in Redis RQ queue so it survives API process restarts.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True

    try:
        # Acquire lock on monitor row to serialize check scheduling
        monitor = (
            db.query(Monitor)
            .filter(Monitor.id == monitor_id)
            .with_for_update()
            .first()
        )
        if not monitor:
            raise ValueError(f"Monitor {monitor_id} not found.")

        # Check for active existing check run (Overlap Prevention)
        active_run = (
            db.query(CheckRun)
            .filter(
                CheckRun.monitor_id == monitor_id,
                CheckRun.state.in_([CheckRunStateEnum.QUEUED, CheckRunStateEnum.RUNNING]),
            )
            .order_by(CheckRun.started_at.desc().nullsfirst())
            .first()
        )
        if active_run:
            # Overlapping check prevented: return the active check run
            return active_run

        check_run_id = uuid.uuid4()
        job_id = f"job-{uuid.uuid4().hex[:12]}"

        check_run = CheckRun(
            id=check_run_id,
            monitor_id=monitor.id,
            job_id=job_id,
            state=CheckRunStateEnum.QUEUED,
            attempt=0,
        )
        db.add(check_run)
        db.commit()
        db.refresh(check_run)

        # Enqueue into durable Redis RQ queue
        q = get_queue("checks", is_async=force_async)
        q.enqueue(
            "app.services.checker.execute_check_job",
            str(check_run.id),
            job_id=job_id,
            job_timeout=60,
            result_ttl=3600,
            failure_ttl=86400,
        )

        return check_run
    finally:
        if owns_db:
            db.close()


def get_rq_job_status(job_id: str) -> Optional[str]:
    """Inspects the state of an RQ job in Redis."""
    try:
        conn = get_redis_connection()
        job = Job.fetch(job_id, connection=conn)
        return job.get_status()
    except Exception:
        return None
