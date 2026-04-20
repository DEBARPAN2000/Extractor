"""Fast-path backend: pypdf for digital (text-based) PDFs.

Zero system dependencies — works out of the box.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from text_extractor.types import ExtractionResult, PageResult

BACKEND_NAME = "pypdf"


def extract(file_path: str | Path) -> ExtractionResult:
    """Extract text from a digital PDF using pypdf."""
    path = Path(file_path)
    reader = PdfReader(path)

    pages: list[PageResult] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        has_images = bool(page.images) if hasattr(page, "images") else False
        pages.append(
            PageResult(
                page_number=i + 1,
                text=text,
                has_images=has_images,
                is_scanned=False,
            )
        )

    metadata = {}
    if reader.metadata:
        meta = reader.metadata
        if meta.title:
            metadata["title"] = meta.title
        if meta.author:
            metadata["author"] = meta.author
        if meta.subject:
            metadata["subject"] = meta.subject
        if meta.creator:
            metadata["creator"] = meta.creator

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=len(pages),
        backend_used=BACKEND_NAME,
        metadata=metadata,
    )


def extract_pages(file_path: str | Path, start: int, end: int) -> ExtractionResult:
    """Extract text from a page range only (1-indexed, inclusive)."""
    path = Path(file_path)
    reader = PdfReader(path)
    total = len(reader.pages)

    start = max(1, start)
    end = min(end, total)

    pages: list[PageResult] = []
    for i in range(start - 1, end):
        page = reader.pages[i]
        text = page.extract_text() or ""
        has_images = bool(page.images) if hasattr(page, "images") else False
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
        total_pages=total,
        backend_used=BACKEND_NAME,
    )


def is_available() -> bool:
    """pypdf is always available (core dependency)."""
    return True
