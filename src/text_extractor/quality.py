"""Text quality detection — detect garbled, corrupt, or low-quality extractions.

Used by the router to decide whether to escalate from fast-path to OCR.
"""

from __future__ import annotations

import unicodedata


def _char_categories(text: str) -> dict[str, int]:
    """Count Unicode general categories in text."""
    cats: dict[str, int] = {}
    for ch in text:
        cat = unicodedata.category(ch)
        cats[cat] = cats.get(cat, 0) + 1
    return cats


def garbled_ratio(text: str) -> float:
    """Estimate what fraction of the text is garbled/non-readable.

    Detects:
    - Control characters (Cc, Cf) excluding common whitespace
    - Private use area chars
    - Combining marks used excessively (modifier letters abused as text)
    - Latin Extended / Greek chars used as substitutes for ASCII

    Returns a float 0.0 (clean) to 1.0 (fully garbled).
    """
    if not text or not text.strip():
        return 0.0

    total = 0
    garbled = 0

    for ch in text:
        if ch in ("\n", "\r", "\t", " "):
            continue
        total += 1
        cp = ord(ch)
        cat = unicodedata.category(ch)

        # Control characters (except whitespace already filtered)
        if cat in ("Cc", "Co"):  # control, private-use
            garbled += 1
            continue

        # Combining marks (Mn, Mc, Me) — normal in some scripts but
        # excessive use signals garbled InDesign output.
        if cat.startswith("M"):
            garbled += 1
            continue

        # Characters from font-encoding abuse ranges:
        # - Latin Extended-A/B when mixed with ASCII
        # - Greek and Coptic (0x0370-0x03FF) used as text substitution
        # - Combining Diacritical Marks (0x0300-0x036F)
        if 0x0100 <= cp <= 0x017F:  # Latin Extended-A
            garbled += 1
            continue
        if 0x0180 <= cp <= 0x024F:  # Latin Extended-B
            garbled += 1
            continue
        if 0x0370 <= cp <= 0x03FF:  # Greek (when not actually Greek text)
            garbled += 1
            continue
        if 0x0300 <= cp <= 0x036F:  # Combining diacriticals
            garbled += 1
            continue

    return garbled / total if total > 0 else 0.0


def is_low_quality(text: str, page_count: int = 1) -> bool:
    """Check if extracted text is likely low quality.

    Criteria:
    - garbled_ratio > 0.15 (>15% suspicious chars)
    - OR very low chars-per-page for a document that should have content
    """
    if not text.strip():
        return True

    # Check garbled ratio
    if garbled_ratio(text) > 0.12:
        return True

    # Very low content density: <50 meaningful chars per page on average
    meaningful = sum(1 for c in text if c.isalnum())
    if page_count > 0 and meaningful / page_count < 50:
        return True

    return False


def text_quality_score(text: str) -> float:
    """Score text quality from 0.0 (garbage) to 1.0 (clean).

    Used for comparing backends on the same document.
    """
    if not text.strip():
        return 0.0
    return max(0.0, 1.0 - garbled_ratio(text))
