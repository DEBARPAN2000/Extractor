"""Core extraction function — the single entry point for all extraction."""

from __future__ import annotations

import time
from pathlib import Path

from text_extractor import cache
from text_extractor.formatter import to_chunks, to_markdown
from text_extractor.router import extract as route_extract
from text_extractor.types import ExtractionResult


def extract_text(
    file_path: str | Path,
    *,
    include_metadata: bool = True,
    max_tokens: int | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """Extract text from a PDF or image file, returned as markdown."""
    result = extract_raw(file_path, start_page=start_page, end_page=end_page)

    if max_tokens:
        chunks = to_chunks(result, max_tokens=max_tokens)
        return chunks[0] if chunks else ""

    return to_markdown(result, include_metadata=include_metadata)


def extract_text_chunked(
    file_path: str | Path,
    *,
    max_tokens: int = 100_000,
    start_page: int | None = None,
    end_page: int | None = None,
) -> list[str]:
    """Extract text and return as token-bounded chunks."""
    result = extract_raw(file_path, start_page=start_page, end_page=end_page)
    return to_chunks(result, max_tokens=max_tokens)


def extract_raw(
    file_path: str | Path,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
) -> ExtractionResult:
    """Extract text and return the raw ExtractionResult dataclass.

    Uses in-memory cache keyed on (path, size, mtime).
    """
    path = Path(file_path)

    use_cache = start_page is None and end_page is None

    # Check cache first for full-document extraction only.
    if use_cache:
        cached = cache.get(path)
        if cached is not None:
            return cached

    result = route_extract(path, start_page=start_page, end_page=end_page)

    # Cache successful full-document results
    if use_cache and not result.error:
        cache.put(path, result)

    return result
