import difflib
import uuid
from io import BytesIO
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageChops, ImageDraw
from pydantic import BaseModel
from app.services.storage import get_screenshot_path, save_screenshot


class TextDiffBlock(BaseModel):
    kind: str  # "equal", "add", "remove"
    text: str


def compute_text_diff(old_text: str, new_text: str) -> List[Dict[str, str]]:
    """
    Computes a human-readable diff of two normalized text documents.
    Returns a structured list of blocks: [{'kind': 'equal|add|remove', 'text': ...}]
    """
    old_lines = old_text.splitlines(keepends=True) if old_text else []
    new_lines = new_text.splitlines(keepends=True) if new_text else []

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    diff_blocks: List[Dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            text = "".join(old_lines[i1:i2])
            if text:
                diff_blocks.append({"kind": "equal", "text": text.rstrip("\n")})
        elif tag == "delete":
            text = "".join(old_lines[i1:i2])
            if text:
                diff_blocks.append({"kind": "remove", "text": text.rstrip("\n")})
        elif tag == "insert":
            text = "".join(new_lines[j1:j2])
            if text:
                diff_blocks.append({"kind": "add", "text": text.rstrip("\n")})
        elif tag == "replace":
            rem_text = "".join(old_lines[i1:i2])
            add_text = "".join(new_lines[j1:j2])
            if rem_text:
                diff_blocks.append({"kind": "remove", "text": rem_text.rstrip("\n")})
            if add_text:
                diff_blocks.append({"kind": "add", "text": add_text.rstrip("\n")})

    return diff_blocks


def compute_screenshot_diff(
    old_img_bytes: bytes,
    new_img_bytes: bytes,
) -> Tuple[bytes, float]:
    """
    Computes a visual diff between two screenshot images using Pillow.
    1. Normalizes image modes (RGBA) and dimensions (resizes to maximum bounding box with background padding).
    2. Calculates per-pixel difference.
    3. Overlays magenta/red highlight on changed pixels atop a dimmed version of the new screenshot.
    Returns (diff_png_bytes, change_ratio).
    """
    old_img = Image.open(BytesIO(old_img_bytes)).convert("RGBA")
    new_img = Image.open(BytesIO(new_img_bytes)).convert("RGBA")

    # Max dimensions to accommodate any slight viewport difference safely
    max_w = max(old_img.width, new_img.width)
    max_h = max(old_img.height, new_img.height)

    # Normalize dimensions safely by padding onto transparent/white canvas
    norm_old = Image.new("RGBA", (max_w, max_h), (255, 255, 255, 0))
    norm_new = Image.new("RGBA", (max_w, max_h), (255, 255, 255, 0))

    norm_old.paste(old_img, (0, 0))
    norm_new.paste(new_img, (0, 0))

    # Calculate difference
    diff = ImageChops.difference(norm_old, norm_new)
    diff_gray = diff.convert("L")

    # Threshold: anything above pixel noise (threshold > 10) is considered changed
    threshold = 10
    mask = diff_gray.point(lambda p: 255 if p > threshold else 0)

    # Calculate change ratio
    mask_bytes = mask.tobytes()
    diff_pixels = sum(1 for b in mask_bytes if b > 0)
    total_pixels = max_w * max_h
    change_ratio = float(diff_pixels) / float(total_pixels) if total_pixels > 0 else 0.0


    # Create composite highlight diff
    # Base is dimmed version of the new screenshot
    dimmed_base = Image.blend(norm_new.convert("RGB"), Image.new("RGB", (max_w, max_h), (255, 255, 255)), 0.3)
    dimmed_rgba = dimmed_base.convert("RGBA")

    # Red/Magenta highlight overlay: (239, 68, 68, 200) - semi-transparent vibrant red
    highlight = Image.new("RGBA", (max_w, max_h), (239, 68, 68, 200))

    # Composite: where mask is non-zero, put highlight
    diff_canvas = Image.composite(highlight, dimmed_rgba, mask)

    # Save to PNG bytes
    out_io = BytesIO()
    diff_canvas.save(out_io, format="PNG")
    return out_io.getvalue(), change_ratio
