"""Docling backend (optional): high-quality extraction for complex PDFs.

Requires optional dependency: docling
Install: pip install text-extractor[docling]
"""

from __future__ import annotations

from pathlib import Path

from text_extractor.types import ExtractionResult, PageResult

BACKEND_NAME = "docling"


def _to_markdown(doc: object) -> str:
    """Best-effort conversion from a Docling document to markdown."""
    for method_name in ("export_to_markdown", "to_markdown", "as_markdown"):
        method = getattr(doc, method_name, None)
        if callable(method):
            try:
                out = method()
                if isinstance(out, str) and out.strip():
                    return out
            except Exception:
                continue

    # Last resort: plain string representation.
    return str(doc)


def _extract_docling_document(path: Path) -> object:
    """Run conversion with Docling and return document-like object."""
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))

    # Some versions return wrapper object with .document field.
    return getattr(result, "document", result)


def extract(file_path: str | Path) -> ExtractionResult:
    """Extract full PDF text using Docling."""
    path = Path(file_path)
    doc = _extract_docling_document(path)
    markdown = _to_markdown(doc)

    pages = [
        PageResult(
            page_number=1,
            text=markdown,
            has_images=False,
            is_scanned=False,
        )
    ]

    metadata: dict = {}
    for attr in ("title", "author", "subject"):
        value = getattr(doc, attr, None)
        if value:
            metadata[attr] = value

    return ExtractionResult(
        source=str(path),
        pages=pages,
        total_pages=1,
        backend_used=BACKEND_NAME,
        metadata=metadata,
    )


def extract_pages(file_path: str | Path, start: int, end: int) -> ExtractionResult:
    """Extract using Docling for compatibility with page-range entry points.

    Note: Docling API does not expose stable, direct page slicing across versions,
    so this backend currently returns full-document markdown in a single page.
    """
    _ = (start, end)
    return extract(file_path)


def is_available() -> bool:
    """Check if Docling is installed."""
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401

        return True
    except Exception:
        return False
