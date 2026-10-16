import os
import uuid
from pathlib import Path
from typing import Optional
from app.config import settings


def get_screenshot_directory(monitor_id: uuid.UUID) -> Path:
    """Returns the base storage directory for a specific monitor's screenshots."""
    base_dir = Path(settings.DATA_DIR).resolve()
    monitor_dir = base_dir / str(monitor_id)
    monitor_dir.mkdir(parents=True, exist_ok=True)
    return monitor_dir


def save_screenshot(monitor_id: uuid.UUID, version_id: uuid.UUID, screenshot_bytes: bytes) -> str:
    """
    Saves screenshot PNG bytes to data/screenshots/<monitor_id>/<version_id>.png
    Returns the relative safe path stored in the database.
    """
    monitor_dir = get_screenshot_directory(monitor_id)
    filename = f"{version_id}.png"
    target_file = monitor_dir / filename

    with open(target_file, "wb") as f:
        f.write(screenshot_bytes)

    # Return relative path
    return f"{monitor_id}/{filename}"


def get_screenshot_path(relative_path: str) -> Optional[Path]:
    """
    Resolves relative screenshot path and enforces path traversal prevention.
    Path must strictly match <uuid>/<uuid>.png.
    """
    base_dir = Path(settings.DATA_DIR).resolve()
    target_path = (base_dir / relative_path).resolve()

    # Enforce path traversal protection: target must be inside base_dir
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        return None

    if target_path.exists() and target_path.is_file():
        return target_path
    return None


def save_diff_screenshot(monitor_id: uuid.UUID, old_version_id: uuid.UUID, new_version_id: uuid.UUID, diff_bytes: bytes) -> str:
    """
    Saves visual diff PNG bytes to data/screenshots/<monitor_id>/diff_<old_version_id>_<new_version_id>.png
    """
    monitor_dir = get_screenshot_directory(monitor_id)
    filename = f"diff_{old_version_id}_{new_version_id}.png"
    target_file = monitor_dir / filename

    with open(target_file, "wb") as f:
        f.write(diff_bytes)

    return f"{monitor_id}/{filename}"


def save_picker_screenshot(monitor_id: uuid.UUID, screenshot_bytes: bytes) -> str:
    """
    Saves picker preview screenshot PNG bytes to data/screenshots/<monitor_id>/picker.png
    """
    monitor_dir = get_screenshot_directory(monitor_id)
    filename = "picker.png"
    target_file = monitor_dir / filename

    with open(target_file, "wb") as f:
        f.write(screenshot_bytes)

    return f"{monitor_id}/{filename}"


def get_picker_screenshot_path(monitor_id: uuid.UUID) -> Optional[Path]:
    """
    Retrieves the path to the picker screenshot if it exists on disk.
    """
    return get_screenshot_path(f"{monitor_id}/picker.png")


def ensure_version_screenshot_cached(version, db) -> Optional[Path]:
    """
    Ensures that the screenshot for a Version exists on local disk.
    1. If it exists on local disk, returns the local Path (and lazily backfills VersionArtifact in DB if missing).
    2. If it does not exist on local disk, queries VersionArtifact in PostgreSQL.
       When found, writes bytes to local disk cache and returns the local Path.
    3. If not found in DB or disk, returns None.
    """
    if not version:
        return None

    # 1. Check if local disk already has it
    if getattr(version, "screenshot_path", None):
        safe_path = get_screenshot_path(version.screenshot_path)
        if safe_path:
            try:
                from app.models.models import VersionArtifact
                has_artifact = db.query(VersionArtifact.version_id).filter(VersionArtifact.version_id == version.id).first()
                if not has_artifact:
                    with open(safe_path, "rb") as f:
                        data = f.read()
                    db.add(VersionArtifact(version_id=version.id, screenshot_bytes=data))
                    db.commit()
            except Exception:
                db.rollback()
            return safe_path

    # 2. Query VersionArtifact from shared database
    try:
        from app.models.models import VersionArtifact
        artifact = db.query(VersionArtifact).filter(VersionArtifact.version_id == version.id).first()
        if artifact and artifact.screenshot_bytes:
            rel_path = save_screenshot(version.monitor_id, version.id, artifact.screenshot_bytes)
            return get_screenshot_path(rel_path)
    except Exception:
        pass

    return None


