"""File-level extraction cache — avoid re-extracting the same file.

Cache key: (file_path, file_size, mtime) → ExtractionResult
In-memory only. No disk persistence (keeps it simple and safe).
"""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from text_extractor.types import ExtractionResult

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, int, float], ExtractionResult] = {}
_lock = Lock()


def _cache_key(path: Path) -> tuple[str, int, float]:
    stat = path.stat()
    return (str(path.resolve()), stat.st_size, stat.st_mtime)


def get(file_path: str | Path) -> ExtractionResult | None:
    """Get cached result if file hasn't changed."""
    path = Path(file_path)
    try:
        key = _cache_key(path)
    except OSError:
        return None

    with _lock:
        result = _cache.get(key)
    if result:
        logger.debug("Cache hit: %s", path.name)
    return result


def put(file_path: str | Path, result: ExtractionResult) -> None:
    """Cache an extraction result."""
    path = Path(file_path)
    try:
        key = _cache_key(path)
    except OSError:
        return

    with _lock:
        _cache[key] = result
    logger.debug("Cached: %s (%d pages)", path.name, result.total_pages)


def clear() -> None:
    """Clear the entire cache."""
    with _lock:
        _cache.clear()
