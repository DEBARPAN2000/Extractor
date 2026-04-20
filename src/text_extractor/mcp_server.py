"""MCP server: exposes text extraction as tools for AI agents.

Usage:
    uvx --from text-extractor text-extractor-mcp
    # or
    python -m text_extractor.mcp_server
"""

from __future__ import annotations

import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from text_extractor.extract import extract_raw, extract_text, extract_text_chunked
from text_extractor.quality import text_quality_score
from text_extractor.router import detect_strategy

mcp = FastMCP(
    "text-extractor",
    instructions="Extract text from PDFs and images. Lightweight, agent-first, zero-config.",
)


@mcp.tool()
def extract_text_from_file(
    file_path: str,
    include_metadata: bool = True,
) -> str:
    """Extract text from a PDF or image file as clean markdown.

    Automatically detects whether the file is a digital PDF, scanned PDF,
    or image, and uses the best available extraction backend.
    Uses quality-aware fallback: pypdf → pdfplumber → pdf2image+OCR.

    Args:
        file_path: Absolute path to a PDF or image file.
        include_metadata: Include document info header (pages, title, etc.).

    Returns:
        Markdown-formatted text content of the document.
    """
    path = Path(file_path)
    if not path.is_absolute():
        return f"Error: Provide an absolute file path. Got: {file_path}"

    t0 = time.perf_counter()
    text = extract_text(path, include_metadata=include_metadata)
    elapsed = time.perf_counter() - t0

    # Append timing footer
    return f"{text}\n\n---\n*Extracted in {elapsed:.1f}s*"


@mcp.tool()
def extract_text_pages(
    file_path: str,
    start_page: int = 1,
    end_page: int | None = None,
) -> str:
    """Extract text from specific pages of a PDF.

    Args:
        file_path: Absolute path to a PDF file.
        start_page: First page to extract (1-indexed).
        end_page: Last page to extract (inclusive). None = all remaining.

    Returns:
        Markdown-formatted text for the requested page range.
    """
    path = Path(file_path)
    if not path.is_absolute():
        return f"Error: Provide an absolute file path. Got: {file_path}"

    t0 = time.perf_counter()
    result = extract_raw(path, start_page=start_page, end_page=end_page)
    if result.error:
        return f"Error: {result.error}"

    selected = result.pages
    start = start_page
    end = end_page or (selected[-1].page_number if selected else start_page)
    if not selected:
        return f"No pages found in range {start}-{end} (document has {result.total_pages} pages)."

    parts = []
    for page in selected:
        if page.text.strip():
            parts.append(f"### Page {page.page_number}\n\n{page.text}")

    elapsed = time.perf_counter() - t0
    text = "\n\n---\n\n".join(parts) if parts else "No text found in the selected pages."
    return f"{text}\n\n---\n*{len(selected)} pages extracted in {elapsed:.1f}s using {result.backend_used}*"


@mcp.tool()
def get_document_info(file_path: str) -> str:
    """Get metadata and structure info about a PDF or image file without extracting full text.

    Useful for understanding a document before extracting. Returns page count,
    detected type (digital/scanned), available metadata, and estimated token count.

    Args:
        file_path: Absolute path to a PDF or image file.

    Returns:
        Markdown-formatted document summary.
    """
    path = Path(file_path)
    if not path.is_absolute():
        return f"Error: Provide an absolute file path. Got: {file_path}"
    if not path.exists():
        return f"Error: File not found: {file_path}"

    t0 = time.perf_counter()
    strategy = detect_strategy(path)
    result = extract_raw(path)
    elapsed = time.perf_counter() - t0

    if result.error:
        return f"Error: {result.error}"

    score = text_quality_score(result.full_text)

    lines = [
        "## Document Info",
        f"- **File:** `{path.name}`",
        f"- **Size:** {path.stat().st_size:,} bytes",
        f"- **Pages:** {result.total_pages}",
        f"- **Strategy:** {strategy}",
        f"- **Backend used:** {result.backend_used}",
        f"- **Total characters:** {result.total_chars:,}",
        f"- **Estimated tokens:** ~{result.estimated_tokens:,}",
        f"- **Text quality:** {score:.0%}",
        f"- **Processing time:** {elapsed:.1f}s",
    ]

    if result.metadata:
        for key, val in result.metadata.items():
            lines.append(f"- **{key.title()}:** {val}")

    scanned_pages = [p for p in result.pages if p.is_scanned]
    if scanned_pages:
        lines.append(f"- **Scanned pages:** {len(scanned_pages)}")

    empty_pages = [p for p in result.pages if not p.text.strip()]
    if empty_pages:
        lines.append(
            f"- **Empty pages:** {len(empty_pages)} "
            f"({', '.join(str(p.page_number) for p in empty_pages[:10])})"
        )

    return "\n".join(lines)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
