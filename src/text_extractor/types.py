"""Shared types for text extraction results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageResult:
    """Extracted content from a single page."""

    page_number: int
    text: str
    char_count: int = 0
    has_images: bool = False
    is_scanned: bool = False

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


@dataclass
class ExtractionResult:
    """Full extraction result for a document."""

    source: str
    pages: list[PageResult] = field(default_factory=list)
    total_pages: int = 0
    backend_used: str = ""
    metadata: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def total_chars(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def estimated_tokens(self) -> int:
        """Rough token estimate (~4 chars per token for English)."""
        return self.total_chars // 4
