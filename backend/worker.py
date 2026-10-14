import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from rq import Worker, Queue
import redis

from app.config import settings
from app.database import SessionLocal
from app.models.models import CheckRun, CheckRunStateEnum

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("worker")


def recover_abandoned_jobs():
    """
    On worker startup, scan for check runs stuck in RUNNING state
    due to ungraceful worker termination or crash, and mark them as ERROR.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        abandoned_runs = db.query(CheckRun).filter(
            CheckRun.state == CheckRunStateEnum.RUNNING,
            CheckRun.started_at < cutoff
        ).all()
        for run in abandoned_runs:
            logger.warning(f"Recovering abandoned run {run.id} for monitor {run.monitor_id}")
            run.state = CheckRunStateEnum.ERROR
            run.error_message = "Worker process interrupted or crashed during check execution"
            run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"Error recovering abandoned jobs: {e}")
        db.rollback()
    finally:
        db.close()


def run_worker():
    logger.info("Initializing RQ Worker...")
    recover_abandoned_jobs()

    redis_conn = redis.from_url(settings.REDIS_URL)
    listen = ["checks"]
    queues = [Queue(name, connection=redis_conn) for name in listen]

    worker = Worker(queues, connection=redis_conn)
    logger.info(f"Worker listening on queue: {listen}")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    run_worker()
