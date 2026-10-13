import re
import hashlib


def normalize_text(raw_text: str) -> str:
    """
    Normalizes extracted text:
    - Normalizes unicode characters
    - Normalizes line breaks
    - Collapses repeated horizontal whitespace (tabs, consecutive spaces) into single spaces
    - Trims leading and trailing whitespace on lines
    - Removes empty lines
    - Preserves case, numbers, dates and substantive wording
    """
    if not raw_text:
        return ""

    # Normalize line breaks to \n
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # Split lines and normalize whitespace on each line
    lines = []
    for line in text.split("\n"):
        # Collapse multiple horizontal whitespace characters to a single space
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned_line:
            lines.append(cleaned_line)

    return "\n".join(lines)


def calculate_content_hash(text: str) -> str:
    """Computes a SHA-256 hexadecimal digest for normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
