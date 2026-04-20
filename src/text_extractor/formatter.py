"""Output formatter: convert ExtractionResult to agent-friendly markdown."""

from __future__ import annotations

from text_extractor.types import ExtractionResult


def to_markdown(result: ExtractionResult, include_metadata: bool = True) -> str:
    """Format an ExtractionResult as clean markdown for LLM consumption."""
    if result.error:
        return f"**Error:** {result.error}"

    parts: list[str] = []

    # Metadata header
    if include_metadata:
        meta_lines = [
            f"- **Source:** `{result.source}`",
            f"- **Pages:** {result.total_pages}",
            f"- **Backend:** {result.backend_used}",
            f"- **Characters:** {result.total_chars:,}",
            f"- **Est. tokens:** ~{result.estimated_tokens:,}",
        ]
        if result.metadata.get("title"):
            meta_lines.insert(0, f"- **Title:** {result.metadata['title']}")
        if result.metadata.get("author"):
            meta_lines.insert(1, f"- **Author:** {result.metadata['author']}")

        parts.append("## Document Info\n" + "\n".join(meta_lines))

    # Page content
    for page in result.pages:
        if not page.text.strip():
            continue

        if result.total_pages > 1:
            parts.append(f"---\n### Page {page.page_number}\n\n{page.text}")
        else:
            parts.append(page.text)

    return "\n\n".join(parts)


def to_chunks(
    result: ExtractionResult,
    max_tokens: int = 100_000,
) -> list[str]:
    """Split extraction result into token-bounded chunks.

    Each chunk is a self-contained markdown string with page boundaries.
    Uses ~4 chars/token estimate.
    """
    if result.error:
        return [f"**Error:** {result.error}"]

    max_chars = max_tokens * 4
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for page in result.pages:
        if not page.text.strip():
            continue

        page_block = f"### Page {page.page_number}\n\n{page.text}"
        page_len = len(page_block)

        if current_len + page_len > max_chars and current_parts:
            chunks.append("\n\n---\n\n".join(current_parts))
            current_parts = []
            current_len = 0

        current_parts.append(page_block)
        current_len += page_len

    if current_parts:
        chunks.append("\n\n---\n\n".join(current_parts))

    return chunks
