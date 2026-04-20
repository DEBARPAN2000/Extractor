"""CLI entry point for text-extractor."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from text_extractor.extract import extract_text, extract_text_chunked
from text_extractor.router import detect_strategy


@click.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--no-metadata", is_flag=True, help="Omit document metadata header.")
@click.option("--pages", type=str, default=None, help="Page range, e.g. '1-5' or '3'.")
@click.option("--chunk-tokens", type=int, default=None, help="Split output into chunks of N tokens.")
@click.option("--info", is_flag=True, help="Show document info only, no text extraction.")
@click.option("--strategy", is_flag=True, help="Show which extraction strategy would be used.")
def main(
    file_path: Path,
    no_metadata: bool,
    pages: str | None,
    chunk_tokens: int | None,
    info: bool,
    strategy: bool,
) -> None:
    """Extract text from a PDF or image file.

    Outputs clean markdown to stdout. Pipe to a file or use with LLM tools.

    Examples:

        text-extractor report.pdf

        text-extractor scan.png

        text-extractor large.pdf --chunk-tokens 50000

        text-extractor report.pdf --pages 1-5

        text-extractor report.pdf --info
    """
    file_path = file_path.resolve()

    if strategy:
        s = detect_strategy(file_path)
        click.echo(f"{file_path.name}: {s}")
        return

    if info:
        from text_extractor.mcp_server import get_document_info

        click.echo(get_document_info(str(file_path)))
        return

    if pages:
        from text_extractor.extract import extract_raw
        from text_extractor.formatter import to_markdown

        # Parse page range
        if "-" in pages:
            start_s, end_s = pages.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(pages)

        result = extract_raw(file_path, start_page=start, end_page=end)
        if result.error:
            click.echo(f"Error: {result.error}", err=True)
            sys.exit(1)

        click.echo(to_markdown(result, include_metadata=not no_metadata))
        return

    if chunk_tokens:
        chunks = extract_text_chunked(file_path, max_tokens=chunk_tokens)
        for i, chunk in enumerate(chunks):
            if i > 0:
                click.echo(f"\n{'=' * 60}\n## Chunk {i + 1}\n{'=' * 60}\n")
            click.echo(chunk)
        return

    output = extract_text(file_path, include_metadata=not no_metadata)
    click.echo(output)


if __name__ == "__main__":
    main()
