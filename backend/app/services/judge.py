import time
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.models import Monitor, CheckRun, CheckRunStateEnum
from app.services.auth import create_judge_session_token
from app.redis_client import redis_client
from app.config import settings

logger = logging.getLogger("judge")

# In-memory IP rate limiter fallback when Redis is unavailable
_in_memory_ip_sessions: Dict[str, list] = {}


def check_ip_session_rate_limit(ip_address: str, max_sessions_per_hour: int = 20) -> None:
    """Enforces per-IP session creation rate limit."""
    if getattr(settings, "TEST_MODE", False):
        return
    now = time.time()
    one_hour_ago = now - 3600

    # Try Redis first
    try:
        redis_key = f"rate:judge_sessions:{ip_address}"
        current = redis_client.incr(redis_key)
        if current == 1:
            redis_client.expire(redis_key, 3600)
        if current > max_sessions_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many evaluation sessions created from this IP address. Please wait before creating another session.",
                    }
                },
            )
        return
    except HTTPException:
        raise
    except Exception:
        pass

    # In-memory fallback
    timestamps = _in_memory_ip_sessions.setdefault(ip_address, [])
    # Prune old
    _in_memory_ip_sessions[ip_address] = [t for t in timestamps if t > one_hour_ago]
    if len(_in_memory_ip_sessions[ip_address]) >= max_sessions_per_hour:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many evaluation sessions created from this IP address. Please wait before creating another session.",
                }
            },
        )
    _in_memory_ip_sessions[ip_address].append(now)


def create_judge_session(client_ip: str) -> Dict[str, Any]:
    """
    Creates an anonymous, scoped, short-lived evaluation session.
    No credentials required.
    """
    check_ip_session_rate_limit(client_ip)

    judge_session_id = secrets.token_hex(16)
    session_lifespan_seconds = 86400  # 24 hours
    token, expires_at = create_judge_session_token(
        judge_session_id=judge_session_id,
        expires_in_seconds=session_lifespan_seconds,
    )

    return {
        "judge_session_id": judge_session_id,
        "session_id": judge_session_id,
        "token": token,
        "expires_at": expires_at,
        "role": "judge",
        "max_monitors": 2,
        "monitor_count": 0,
        "limits": {
            "max_monitors": 2,
            "min_interval_minutes": 15,
            "max_manual_checks_per_hour": 3,
            "session_ttl_hours": 24,
        },
    }


def enforce_judge_monitor_limit(db: Session, judge_session_id: str) -> None:
    """Limits judge sessions to at most 2 monitors."""
    count = db.query(Monitor).filter(Monitor.judge_session_id == judge_session_id).count()
    if count >= 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MONITOR_LIMIT_REACHED",
                    "message": "Evaluation quota reached: A maximum of 2 monitors is permitted per judge session.",
                }
            },
        )


def enforce_judge_manual_check_rate_limit(db: Session, monitor: Monitor) -> None:
    """
    Enforces server-side quota on manual check execution:
    1. Global concurrent anonymous check cap (max 5 concurrent).
    2. Per-monitor hourly quota (max 3 checks per hour).
    """
    if not monitor.judge_session_id:
        return

    now = datetime.now(timezone.utc)

    # 1. Global cap on concurrent or queued anonymous checks (within last 10 minutes)
    if not getattr(settings, "TEST_MODE", False):
        recent_cutoff = now - timedelta(minutes=10)
        active_anonymous_checks = (
            db.query(CheckRun)
            .join(Monitor, CheckRun.monitor_id == Monitor.id)
            .filter(
                Monitor.judge_session_id.isnot(None),
                CheckRun.state.in_([CheckRunStateEnum.QUEUED, CheckRunStateEnum.RUNNING]),
                or_(CheckRun.started_at.is_(None), CheckRun.started_at >= recent_cutoff),
            )
            .count()
        )
        if active_anonymous_checks >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "CONCURRENCY_CAP_REACHED",
                        "message": "High evaluation traffic: Multiple browser captures are currently executing. Please wait a moment and try again.",
                    }
                },
            )

    # 2. Hourly check quota per monitor
    window_start = monitor.manual_checks_window_start
    count = monitor.manual_checks_count or 0

    if not window_start or (now - window_start) >= timedelta(hours=1):
        # Reset hourly window
        monitor.manual_checks_window_start = now
        monitor.manual_checks_count = 1
        db.commit()
    elif count >= 3:
        mins_remaining = max(1, int(60 - (now - window_start).total_seconds() / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "CHECK_QUOTA_EXCEEDED",
                    "message": f"Evaluation check quota reached: Maximum 3 manual checks per monitor per hour. Please wait {mins_remaining} minute(s) or let automatic 15-minute background monitoring run.",
                }
            },
        )
    else:
        monitor.manual_checks_count = count + 1
        db.commit()


def cleanup_expired_judge_monitors(db: Session) -> int:
    """
    Finds and disables judge monitors whose evaluation session has expired.
    """
    now = datetime.now(timezone.utc)
    updated = (
        db.query(Monitor)
        .filter(
            Monitor.judge_session_id.isnot(None),
            Monitor.expires_at.isnot(None),
            Monitor.expires_at <= now,
            Monitor.enabled.is_(True),
        )
        .update({"enabled": False}, synchronize_session=False)
    )
    if updated:
        db.commit()
    return updated
