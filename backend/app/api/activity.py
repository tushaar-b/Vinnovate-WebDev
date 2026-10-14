import uuid
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.models import (
    CheckRun,
    CheckRunStateEnum,
    NotificationOutbox,
    OutboxStateEnum,
    Monitor,
    NotificationChannel,
)
from app.schemas.activity import ActivityItem, ActivityListResponse

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=ActivityListResponse)
def get_activity_feed(
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None, description="Filter by event_type or status"),
    monitor_id: Optional[uuid.UUID] = Query(None, description="Filter by monitor UUID"),
    db: Session = Depends(get_db),
):
    """
    Returns unified real database-backed activity stream:
    - baseline_created
    - content_changed
    - content_unchanged
    - monitoring_failed
    - monitoring_blocked
    - alert_delivered
    - alert_failed
    """
    items: List[ActivityItem] = []

    # 1. Query CheckRuns
    check_query = (
        db.query(CheckRun)
        .join(Monitor, CheckRun.monitor_id == Monitor.id)
        .options(joinedload(CheckRun.monitor), joinedload(CheckRun.version))
        .filter(CheckRun.state.notin_([CheckRunStateEnum.QUEUED, CheckRunStateEnum.RUNNING]))
    )
    if monitor_id:
        check_query = check_query.filter(CheckRun.monitor_id == monitor_id)

    # 2. Query Notification Outbox
    outbox_query = (
        db.query(NotificationOutbox)
        .join(Monitor, NotificationOutbox.monitor_id == Monitor.id)
        .options(joinedload(NotificationOutbox.monitor), joinedload(NotificationOutbox.channel))
        .filter(NotificationOutbox.state.in_([OutboxStateEnum.SENT, OutboxStateEnum.FAILED]))
    )
    if monitor_id:
        outbox_query = outbox_query.filter(NotificationOutbox.monitor_id == monitor_id)

    # Fetch recent records from both
    recent_checks = check_query.order_by(CheckRun.finished_at.desc().nullslast()).limit(limit * 2).all()
    recent_outbox = outbox_query.order_by(NotificationOutbox.created_at.desc()).limit(limit * 2).all()

    for r in recent_checks:
        mon = r.monitor
        if not mon:
            continue
        ts = r.finished_at or r.started_at or datetime.now()

        if r.state == CheckRunStateEnum.BASELINE:
            item = ActivityItem(
                id=f"check-{r.id}",
                event_type="baseline_created",
                status="baseline",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title="Baseline Created",
                summary=f"Initial version captured for {mon.name}.",
                version_id=r.version.id if r.version else None,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"http_status": r.http_status, "duration_ms": r.duration_ms},
            )
            items.append(item)

        elif r.state == CheckRunStateEnum.CHANGED:
            v_seq = r.version.sequence_number if r.version else ""
            item = ActivityItem(
                id=f"check-{r.id}",
                event_type="content_changed",
                status="changed",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title=f"Content Changed (v{v_seq})" if v_seq else "Content Changed",
                summary=f"Confirmed content update detected on {mon.name}.",
                version_id=r.version.id if r.version else None,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"http_status": r.http_status, "duration_ms": r.duration_ms},
            )
            items.append(item)

        elif r.state == CheckRunStateEnum.UNCHANGED:
            item = ActivityItem(
                id=f"check-{r.id}",
                event_type="content_unchanged",
                status="unchanged",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title="Content Unchanged",
                summary="Check completed. No differences from current baseline.",
                version_id=None,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"http_status": r.http_status, "duration_ms": r.duration_ms},
            )
            items.append(item)

        elif r.state == CheckRunStateEnum.ERROR:
            item = ActivityItem(
                id=f"check-{r.id}",
                event_type="monitoring_failed",
                status="error",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title="Monitoring Failed",
                summary=r.error_message or f"Check failed with error: {r.error_code or 'UNKNOWN'}",
                version_id=None,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"error_code": r.error_code, "http_status": r.http_status},
            )
            items.append(item)

        elif r.state == CheckRunStateEnum.BLOCKED:
            item = ActivityItem(
                id=f"check-{r.id}",
                event_type="monitoring_blocked",
                status="blocked",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title="Monitoring Blocked",
                summary=r.error_message or "Request blocked by SSRF or security policy.",
                version_id=None,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"error_code": r.error_code, "http_status": r.http_status},
            )
            items.append(item)

    for o in recent_outbox:
        mon = o.monitor
        if not mon:
            continue
        ch = o.channel
        ch_type = ch.channel_type.value if ch else "channel"
        ts = o.sent_at or o.created_at

        if o.state == OutboxStateEnum.SENT:
            item = ActivityItem(
                id=f"outbox-{o.id}",
                event_type="alert_delivered",
                status="delivered",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title=f"Alert Delivered ({ch_type.capitalize()})",
                summary=f"Notification delivered via {ch_type} for {mon.name}.",
                version_id=o.version_id,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"channel_type": ch_type, "attempts": o.attempts},
            )
            items.append(item)
        elif o.state == OutboxStateEnum.FAILED:
            item = ActivityItem(
                id=f"outbox-{o.id}",
                event_type="alert_failed",
                status="failed",
                monitor_id=mon.id,
                monitor_name=mon.name,
                monitor_url=mon.url,
                timestamp=ts,
                title=f"Alert Failed ({ch_type.capitalize()})",
                summary=f"Failed to deliver notification via {ch_type}: {o.last_error or 'Delivery error'}",
                version_id=o.version_id,
                comparison_url=f"#monitors/{mon.id}",
                metadata={"channel_type": ch_type, "attempts": o.attempts, "error": o.last_error},
            )
            items.append(item)

    # Sort unified feed chronologically descending
    items.sort(key=lambda x: x.timestamp, reverse=True)

    # Filter by event_type or status if specified
    if event_type and event_type != "all":
        evt_lower = event_type.lower()
        items = [i for i in items if i.event_type == evt_lower or i.status == evt_lower]

    limited = items[:limit]
    return ActivityListResponse(items=limited, total=len(limited))
