"""Fast, high-quality backend: PyMuPDF (fitz) for digital PDFs.

PyMuPDF is 10-20x faster than pypdf and correctly handles custom font
encodings (CMap-mapped glyphs) that cause pypdf/pdfplumber to emit
(cid:N) artifacts.

Optional dependency — install with:
    pip install "text-extractor-lightweight[fast]"
or directly:
    pip install pymupdf
"""

from __future__ import annotations

from pathlib import Path

from text_extractor.types import ExtractionResult, PageResult

BACKEND_NAME = "pymupdf"


def extract(file_path: str | Path) -> ExtractionResult:
    """Extract text from a digital PDF using PyMuPDF."""
    import fitz  # pymupdf

    path = Path(file_path)
    pages: list[PageResult] = []
    metadata: dict = {}

    doc = fitz.open(str(path))
    try:
        meta = doc.metadata or {}
        for key in ("title", "author", "subject", "creator"):
            val = meta.get(key, "").strip()
            if val:
                metadata[key] = val

        for i, page in enumerate(doc):
            text = page.get_text()
            has_images = bool(page.get_images())
            pages.append(
                PageResult(
                    page_number=i + 1,
                    text=text,
                    has_images=has_images,
                    is_scanned=False,
                )
            )
    finally:
        doc.close()

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=len(pages),
        backend_used=BACKEND_NAME,
        metadata=metadata,
    )


def extract_pages(file_path: str | Path, start: int, end: int) -> ExtractionResult:
    """Extract a page range only (1-indexed, inclusive)."""
    import fitz  # pymupdf

    path = Path(file_path)
    pages: list[PageResult] = []

    doc = fitz.open(str(path))
    try:
        total = len(doc)
        end = min(end, total)
        for i in range(start - 1, end):
            page = doc[i]
            text = page.get_text()
            pages.append(
                PageResult(
                    page_number=i + 1,
                    text=text,
                    has_images=bool(page.get_images()),
                    is_scanned=False,
                )
            )
    finally:
        doc.close()

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=total,
        backend_used=BACKEND_NAME,
    )


def is_available() -> bool:
    """Check if pymupdf (fitz) is installed."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False
