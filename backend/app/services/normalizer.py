import re
import hashlib
import unicodedata


def normalize_text(raw_text: str) -> str:
    """
    Normalizes extracted text:
    - Normalizes unicode characters (NFKC normalization converts non-breaking spaces, fullwidth characters, etc.)
    - Normalizes line breaks to \n
    - Collapses repeated horizontal whitespace (tabs, consecutive spaces, non-breaking spaces) into single spaces
    - Trims leading and trailing whitespace on lines
    - Removes empty lines
    - Preserves case, numbers, dates, prices, SKUs and substantive wording
    """
    if not raw_text:
        return ""

    # Normalize unicode to ensure consistent representation across captures
    text = unicodedata.normalize("NFKC", raw_text)

    # Normalize line breaks to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split lines and normalize whitespace on each line
    lines = []
    for line in text.split("\n"):
        # Collapse multiple horizontal whitespace characters (including unicode spaces) to a single space
        cleaned_line = re.sub(r"[ \t\u00a0\u2000-\u200b\u202f\u205f\u3000]+", " ", line).strip()
        if cleaned_line:
            lines.append(cleaned_line)

    return "\n".join(lines)


def calculate_content_hash(text: str) -> str:
    """Computes a SHA-256 hexadecimal digest for normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
