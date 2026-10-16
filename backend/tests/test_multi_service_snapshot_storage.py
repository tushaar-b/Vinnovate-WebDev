import io
import uuid
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.models import Monitor, Version, VersionArtifact, SensitivityEnum
from app.services.storage import ensure_version_screenshot_cached, save_screenshot
from app.services.auth import create_session_token

client = TestClient(app)


def create_sample_png_bytes(color: str = "red", width: int = 1440, height: int = 900) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_multi_service_snapshot_isolated_storage():
    """
    Simulates Railway distributed multi-service architecture:
    1. Worker service captures webpage, writes screenshot to PostgreSQL VersionArtifact
       and to worker-local disk.
    2. API service starts with an isolated/clean DATA_DIR (worker disk NOT shared).
    3. User visits Snapshot Overview directly -> API must retrieve screenshot from VersionArtifact,
       cache it to API local disk, and serve valid image/png bytes without requiring any visit
       to Region Picker or Visual Overlay Diff.
    4. Opening Region Picker does NOT overwrite Version's screenshot.
    5. Older versions load their own distinct screenshots correctly.
    """
    db = SessionLocal()
    token, _ = create_session_token("admin")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Create temporary isolated directory simulating API service container
    api_temp_data_dir = tempfile.mkdtemp(prefix="api_isolated_data_")
    original_data_dir = settings.DATA_DIR

    try:
        # Create a monitor
        monitor_id = uuid.uuid4()
        monitor = Monitor(
            id=monitor_id,
            name="Amazon India Test Product",
            url="https://www.amazon.in/dp/B08L5VJYV7",
            canonical_url="https://www.amazon.in/dp/B08L5VJYV7",
            interval_minutes=15,
            sensitivity=SensitivityEnum.MEDIUM,
            enabled=True,
        )
        db.add(monitor)

        # Worker generates Version #1
        v1_id = uuid.uuid4()
        v1_png = create_sample_png_bytes(color="blue", width=1440, height=900)
        v1 = Version(
            id=v1_id,
            monitor_id=monitor_id,
            sequence_number=1,
            content_hash="v1_hash_12345",
            normalized_text="Apple iPhone 13 (128GB) - Blue\nPrice: Rs. 49,999",
            screenshot_path=f"{monitor_id}/{v1_id}.png",
        )
        db.add(v1)
        db.add(VersionArtifact(version_id=v1_id, screenshot_bytes=v1_png))

        # Worker generates Version #2 (latest)
        v2_id = uuid.uuid4()
        v2_png = create_sample_png_bytes(color="green", width=1440, height=900)
        v2 = Version(
            id=v2_id,
            monitor_id=monitor_id,
            sequence_number=2,
            content_hash="v2_hash_67890",
            normalized_text="Apple iPhone 13 (128GB) - Blue\nPrice: Rs. 47,999",
            screenshot_path=f"{monitor_id}/{v2_id}.png",
        )
        db.add(v2)
        db.add(VersionArtifact(version_id=v2_id, screenshot_bytes=v2_png))
        db.commit()

        # Switch DATA_DIR to simulated API service container (which does NOT have files on disk)
        settings.DATA_DIR = api_temp_data_dir

        # STEP 1: Verify disk is completely empty on the API service
        api_v2_file = Path(api_temp_data_dir) / str(monitor_id) / f"{v2_id}.png"
        assert not api_v2_file.exists(), "Test precondition failed: API disk should not have worker files yet."

        # STEP 2: Unauthenticated request must be rejected
        settings.TEST_AUTH_ENABLED = True
        res_unauth = client.get(f"/api/versions/{v2_id}/screenshot")
        assert res_unauth.status_code == 401

        # STEP 3: Request latest version screenshot directly with session token via query param
        # (exactly as the Snapshot Overview <img> tag does in production)
        res_overview = client.get(f"/api/versions/{v2_id}/screenshot?token={token}")
        assert res_overview.status_code == 200, f"Expected 200, got {res_overview.status_code}: {res_overview.text}"
        assert res_overview.headers["content-type"] == "image/png"
        assert res_overview.content[:8] == b"\x89PNG\r\n\x1a\n", "Response body is not valid PNG bytes."

        # Verify image dimensions
        img = Image.open(io.BytesIO(res_overview.content))
        assert img.size == (1440, 900)

        # STEP 4: Confirm file is now cached on API local disk for high performance
        assert api_v2_file.exists()
        assert api_v2_file.read_bytes() == v2_png

        # STEP 5: Request older version screenshot directly (Version #1)
        res_v1 = client.get(f"/api/versions/{v1_id}/screenshot?token={token}")
        assert res_v1.status_code == 200
        assert res_v1.headers["content-type"] == "image/png"
        assert res_v1.content == v1_png
        img_v1 = Image.open(io.BytesIO(res_v1.content))
        assert img_v1.size == (1440, 900)

        # STEP 6: Verify Visual Diff image computation works across multi-service architecture
        res_diff = client.get(f"/api/monitors/{monitor_id}/diff-image/{v1_id}/{v2_id}?token={token}")
        assert res_diff.status_code == 200
        assert res_diff.headers["content-type"] == "image/png"
        assert res_diff.content[:8] == b"\x89PNG\r\n\x1a\n"

        # STEP 7: Verify Region Picker screenshot route does NOT corrupt version screenshots
        picker_png = create_sample_png_bytes(color="yellow", width=1440, height=900)
        from app.services.storage import save_picker_screenshot
        save_picker_screenshot(monitor_id, picker_png)

        # Picker screenshot route returns picker screenshot
        res_picker_img = client.get(f"/api/monitors/{monitor_id}/picker/screenshot?token={token}")
        assert res_picker_img.status_code == 200
        assert res_picker_img.content == picker_png

        # Version 2 screenshot remains UNCHANGED (not overwritten by picker)
        res_v2_check = client.get(f"/api/versions/{v2_id}/screenshot?token={token}")
        assert res_v2_check.status_code == 200
        assert res_v2_check.content == v2_png, "Version 2 screenshot was corrupted or overwritten!"

    finally:
        # Cleanup
        settings.TEST_AUTH_ENABLED = False
        settings.DATA_DIR = original_data_dir
        shutil.rmtree(api_temp_data_dir, ignore_errors=True)
        # Clean up test DB records
        try:
            db.query(VersionArtifact).filter(VersionArtifact.version_id.in_([v1_id, v2_id])).delete(synchronize_session=False)
            db.query(Version).filter(Version.monitor_id == monitor_id).delete(synchronize_session=False)
            db.query(Monitor).filter(Monitor.id == monitor_id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
