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


