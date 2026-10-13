import uuid
from datetime import timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.models import (
    Monitor,
    CheckRun,
    Version,
    CheckRunStateEnum,
    utc_now,
)
from app.schemas.monitors import (
    MonitorCreate,
    MonitorUpdate,
    MonitorSummary,
    MonitorDetail,
    MonitorListResponse,
    CheckRunResponse,
    CheckRunListResponse,
    CheckEnqueueResponse,
    VersionSummary,
    VersionDetails,
    VersionListResponse,
    VersionComparisonResponse,
    TextDiffItem,
)
from app.services.security import validate_target_url, canonicalize_url
from app.services.checker import execute_check
from app.services.storage import get_screenshot_path, save_diff_screenshot
from app.services.diff import compute_text_diff, compute_screenshot_diff

router = APIRouter(tags=["Monitors"])


def get_monitor_versions_count(db: Session, monitor_id: uuid.UUID) -> int:
    return db.query(func.count(Version.id)).filter(Version.monitor_id == monitor_id).scalar() or 0


@router.get("/monitors", response_model=MonitorListResponse)
def list_monitors(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    total = db.query(func.count(Monitor.id)).scalar() or 0
    monitors = (
        db.query(Monitor)
        .order_by(Monitor.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for m in monitors:
        v_count = get_monitor_versions_count(db, m.id)
        summary = MonitorSummary(
            id=m.id,
            name=m.name,
            url=m.url,
            interval_minutes=m.interval_minutes,
            sensitivity=m.sensitivity,
            enabled=m.enabled,
            status=m.status,
            last_checked_at=m.last_checked_at,
            last_changed_at=m.last_changed_at,
            next_check_at=m.next_check_at,
            last_error=m.last_error,
            versions_count=v_count,
            created_at=m.created_at,
        )
        items.append(summary)

    return MonitorListResponse(items=items, total=total)


@router.post("/monitors", response_model=MonitorDetail, status_code=status.HTTP_201_CREATED)
def create_monitor(
    payload: MonitorCreate,
    db: Session = Depends(get_db),
):
    # Enforce SSRF validation
    is_safe, error_reason = validate_target_url(payload.url)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "BLOCKED_TARGET", "message": error_reason}},
        )

    canonical = canonicalize_url(payload.url)

    monitor = Monitor(
        name=payload.name,
        url=payload.url,
        canonical_url=canonical,
        interval_minutes=payload.interval_minutes,
        sensitivity=payload.sensitivity,
        enabled=True,
        next_check_at=utc_now(),
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)

    return MonitorDetail(
        id=monitor.id,
        name=monitor.name,
        url=monitor.url,
        canonical_url=monitor.canonical_url,
        interval_minutes=monitor.interval_minutes,
        sensitivity=monitor.sensitivity,
        enabled=monitor.enabled,
        status=monitor.status,
        last_checked_at=monitor.last_checked_at,
        last_changed_at=monitor.last_changed_at,
        next_check_at=monitor.next_check_at,
        last_error=monitor.last_error,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
        versions_count=0,
        rules=[],
    )


@router.get("/monitors/{monitor_id}", response_model=MonitorDetail)
def get_monitor(monitor_id: uuid.UUID, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found."}},
        )

    v_count = get_monitor_versions_count(db, monitor.id)
    return MonitorDetail(
        id=monitor.id,
        name=monitor.name,
        url=monitor.url,
        canonical_url=monitor.canonical_url,
        interval_minutes=monitor.interval_minutes,
        sensitivity=monitor.sensitivity,
        enabled=monitor.enabled,
        status=monitor.status,
        last_checked_at=monitor.last_checked_at,
        last_changed_at=monitor.last_changed_at,
        next_check_at=monitor.next_check_at,
        last_error=monitor.last_error,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
        versions_count=v_count,
        rules=monitor.rules,
    )


@router.patch("/monitors/{monitor_id}", response_model=MonitorDetail)
def update_monitor(
    monitor_id: uuid.UUID,
    payload: MonitorUpdate,
    db: Session = Depends(get_db),
):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found."}},
        )

    if payload.name is not None:
        monitor.name = payload.name
    if payload.interval_minutes is not None:
        monitor.interval_minutes = payload.interval_minutes
        monitor.next_check_at = utc_now() + timedelta(minutes=payload.interval_minutes)
    if payload.sensitivity is not None:
        monitor.sensitivity = payload.sensitivity
    if payload.enabled is not None:
        monitor.enabled = payload.enabled

    db.commit()
    db.refresh(monitor)
    v_count = get_monitor_versions_count(db, monitor.id)

    return MonitorDetail(
        id=monitor.id,
        name=monitor.name,
        url=monitor.url,
        canonical_url=monitor.canonical_url,
        interval_minutes=monitor.interval_minutes,
        sensitivity=monitor.sensitivity,
        enabled=monitor.enabled,
        status=monitor.status,
        last_checked_at=monitor.last_checked_at,
        last_changed_at=monitor.last_changed_at,
        next_check_at=monitor.next_check_at,
        last_error=monitor.last_error,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
        versions_count=v_count,
        rules=monitor.rules,
    )


@router.delete("/monitors/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monitor(monitor_id: uuid.UUID, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found."}},
        )

    db.delete(monitor)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/monitors/{monitor_id}/checks",
    response_model=CheckEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def queue_manual_check(
    monitor_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found."}},
        )

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

    # Enqueue background task (asynchronous, non-blocking)
    background_tasks.add_task(execute_check, check_run_id)

    return CheckEnqueueResponse(
        check_run_id=check_run_id,
        job_id=job_id,
        state="queued",
    )


@router.get("/monitors/{monitor_id}/checks", response_model=CheckRunListResponse)
def list_monitor_checks(
    monitor_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(CheckRun)
        .filter(CheckRun.monitor_id == monitor_id)
        .order_by(CheckRun.started_at.desc().nulls_last())
        .limit(limit)
        .all()
    )

    items = [
        CheckRunResponse(
            id=r.id,
            monitor_id=r.monitor_id,
            state=r.state,
            started_at=r.started_at,
            finished_at=r.finished_at,
            http_status=r.http_status,
            error_code=r.error_code,
            error_message=r.error_message,
            duration_ms=r.duration_ms,
            version_id=r.version.id if r.version else None,
        )
        for r in runs
    ]
    return CheckRunListResponse(items=items)


@router.get("/checks/{check_run_id}", response_model=CheckRunResponse)
def get_check_run(check_run_id: uuid.UUID, db: Session = Depends(get_db)):
    r = db.query(CheckRun).filter(CheckRun.id == check_run_id).first()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Check run not found."}},
        )

    return CheckRunResponse(
        id=r.id,
        monitor_id=r.monitor_id,
        state=r.state,
        started_at=r.started_at,
        finished_at=r.finished_at,
        http_status=r.http_status,
        error_code=r.error_code,
        error_message=r.error_message,
        duration_ms=r.duration_ms,
        version_id=r.version.id if r.version else None,
    )


@router.get("/monitors/{monitor_id}/versions", response_model=VersionListResponse)
def list_monitor_versions(monitor_id: uuid.UUID, db: Session = Depends(get_db)):
    versions = (
        db.query(Version)
        .filter(Version.monitor_id == monitor_id)
        .order_by(Version.sequence_number.desc())
        .all()
    )

    items = [
        VersionSummary(
            id=v.id,
            monitor_id=v.monitor_id,
            sequence_number=v.sequence_number,
            captured_at=v.captured_at,
            content_hash=v.content_hash,
            screenshot_url=f"/api/versions/{v.id}/screenshot",
            short_preview=v.normalized_text[:250].strip() if v.normalized_text else "",
        )
        for v in versions
    ]
    return VersionListResponse(items=items)


@router.get("/monitors/{monitor_id}/versions/{version_id}", response_model=VersionDetails)
def get_version_details(
    monitor_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    v = (
        db.query(Version)
        .filter(Version.monitor_id == monitor_id, Version.id == version_id)
        .first()
    )
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Version not found."}},
        )

    return VersionDetails(
        id=v.id,
        monitor_id=v.monitor_id,
        sequence_number=v.sequence_number,
        captured_at=v.captured_at,
        content_hash=v.content_hash,
        screenshot_url=f"/api/versions/{v.id}/screenshot",
        short_preview=v.normalized_text[:250].strip() if v.normalized_text else "",
        normalized_text=v.normalized_text,
    )


@router.get("/versions/{version_id}/screenshot")
def get_version_screenshot(version_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.query(Version).filter(Version.id == version_id).first()
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Version not found."}},
        )

    safe_path = get_screenshot_path(v.screenshot_path)
    if not safe_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Screenshot file not found on disk."}},
        )

    return FileResponse(path=safe_path, media_type="image/png")


@router.get("/monitors/{monitor_id}/compare", response_model=VersionComparisonResponse)
def compare_versions(
    monitor_id: uuid.UUID,
    from_version_id: uuid.UUID = Query(..., alias="from", description="Base / older version UUID"),
    to_version_id: uuid.UUID = Query(..., alias="to", description="Target / newer version UUID"),
    db: Session = Depends(get_db),
):
    # Verify monitor exists
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Monitor not found."}},
        )

    # Fetch both versions and verify they belong to this monitor
    v_old = (
        db.query(Version)
        .filter(Version.monitor_id == monitor_id, Version.id == from_version_id)
        .first()
    )
    v_new = (
        db.query(Version)
        .filter(Version.monitor_id == monitor_id, Version.id == to_version_id)
        .first()
    )

    if not v_old or not v_new:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "One or both requested versions not found for this monitor.",
                }
            },
        )

    # Compute text diff
    text_diff_raw = compute_text_diff(v_old.normalized_text, v_new.normalized_text)
    text_diff = [TextDiffItem(**item) for item in text_diff_raw]

    # Compute visual diff if screenshot files exist
    image_old_url = f"/api/versions/{v_old.id}/screenshot"
    image_new_url = f"/api/versions/{v_new.id}/screenshot"
    image_diff_url: Optional[str] = None
    change_ratio = 0.0

    old_path = get_screenshot_path(v_old.screenshot_path)
    new_path = get_screenshot_path(v_new.screenshot_path)

    if old_path and new_path:
        try:
            diff_filename = f"diff_{v_old.id}_{v_new.id}.png"
            diff_rel_path = f"{monitor_id}/{diff_filename}"
            existing_diff = get_screenshot_path(diff_rel_path)

            with open(old_path, "rb") as f1, open(new_path, "rb") as f2:
                diff_png_bytes, change_ratio = compute_screenshot_diff(f1.read(), f2.read())

            if not existing_diff:
                save_diff_screenshot(monitor_id, v_old.id, v_new.id, diff_png_bytes)

            image_diff_url = f"/api/monitors/{monitor_id}/diff-image/{v_old.id}/{v_new.id}"
        except Exception:
            # Fall back gracefully if image computation fails
            image_diff_url = None


    old_details = VersionDetails(
        id=v_old.id,
        monitor_id=v_old.monitor_id,
        sequence_number=v_old.sequence_number,
        captured_at=v_old.captured_at,
        content_hash=v_old.content_hash,
        screenshot_url=image_old_url,
        short_preview=v_old.normalized_text[:250].strip() if v_old.normalized_text else "",
        normalized_text=v_old.normalized_text,
    )

    new_details = VersionDetails(
        id=v_new.id,
        monitor_id=v_new.monitor_id,
        sequence_number=v_new.sequence_number,
        captured_at=v_new.captured_at,
        content_hash=v_new.content_hash,
        screenshot_url=image_new_url,
        short_preview=v_new.normalized_text[:250].strip() if v_new.normalized_text else "",
        normalized_text=v_new.normalized_text,
    )

    return VersionComparisonResponse(
        old_version=old_details,
        new_version=new_details,
        text_diff=text_diff,
        image_old_url=image_old_url,
        image_new_url=image_new_url,
        image_diff_url=image_diff_url,
        change_ratio=change_ratio,
    )


@router.get("/monitors/{monitor_id}/diff-image/{old_id}/{new_id}")
def get_diff_image(
    monitor_id: uuid.UUID,
    old_id: uuid.UUID,
    new_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    diff_rel_path = f"{monitor_id}/diff_{old_id}_{new_id}.png"
    safe_path = get_screenshot_path(diff_rel_path)
    if not safe_path:
        # Generate on the fly if needed
        v_old = db.query(Version).filter(Version.monitor_id == monitor_id, Version.id == old_id).first()
        v_new = db.query(Version).filter(Version.monitor_id == monitor_id, Version.id == new_id).first()
        if not v_old or not v_new:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Versions not found."}},
            )
        old_path = get_screenshot_path(v_old.screenshot_path)
        new_path = get_screenshot_path(v_new.screenshot_path)
        if not old_path or not new_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Screenshots not found on disk."}},
            )
        with open(old_path, "rb") as f1, open(new_path, "rb") as f2:
            diff_png_bytes, _ = compute_screenshot_diff(f1.read(), f2.read())
        save_diff_screenshot(monitor_id, old_id, new_id, diff_png_bytes)
        safe_path = get_screenshot_path(diff_rel_path)

    if not safe_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Diff image could not be loaded."}},
        )

    return FileResponse(path=safe_path, media_type="image/png")

