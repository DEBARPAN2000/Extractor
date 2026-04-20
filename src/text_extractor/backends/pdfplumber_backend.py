"""pdfplumber backend: better text extraction for PDFs with complex font encodings.

Handles InDesign custom font mappings that break pypdf.
Requires optional dep: pdfplumber
"""

from __future__ import annotations

import logging
from pathlib import Path

from text_extractor.types import ExtractionResult, PageResult

BACKEND_NAME = "pdfplumber"
logger = logging.getLogger(__name__)


def extract(file_path: str | Path) -> ExtractionResult:
    """Extract text using pdfplumber (better font decoding)."""
    import pdfplumber

    path = Path(file_path)
    pages: list[PageResult] = []
    metadata: dict = {}

    with pdfplumber.open(path) as pdf:
        if pdf.metadata:
            for key in ("Title", "Author", "Subject", "Creator"):
                val = pdf.metadata.get(key)
                if val:
                    metadata[key.lower()] = val

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            has_images = bool(page.images)
            pages.append(
                PageResult(
                    page_number=i + 1,
                    text=text,
                    has_images=has_images,
                    is_scanned=False,
                )
            )

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=len(pages),
        backend_used=BACKEND_NAME,
        metadata=metadata,
    )


def extract_pages(file_path: str | Path, start: int, end: int) -> ExtractionResult:
    """Extract specific pages only (avoids processing entire document)."""
    import pdfplumber

    path = Path(file_path)
    pages: list[PageResult] = []

    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        end = min(end, total)
        for i in range(start - 1, end):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            pages.append(
                PageResult(
                    page_number=i + 1,
                    text=text,
                    has_images=bool(page.images),
                    is_scanned=False,
                )
            )

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=total,
        backend_used=BACKEND_NAME,
    )


def is_available() -> bool:
    """Check if pdfplumber is installed."""
    try:
        import pdfplumber  # noqa: F401
        return True
    except ImportError:
        return False
