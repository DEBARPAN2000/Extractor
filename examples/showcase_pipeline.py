"""Showcase pipeline for text-extractor-lightweight.

This script demonstrates an end-to-end extraction flow suitable for demos:
1) detect routing strategy,
2) run extraction,
3) compute quality metrics,
4) save markdown + JSON artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from text_extractor.extract import extract_raw
from text_extractor.formatter import to_markdown
from text_extractor.quality import cid_ratio, text_quality_score
from text_extractor.router import detect_strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the text extractor showcase pipeline.")
    parser.add_argument("file", type=Path, help="Path to input PDF/image file.")
    parser.add_argument("--out", type=Path, default=Path("showcase_output"), help="Output directory.")
    parser.add_argument("--start-page", type=int, default=None, help="Start page (1-indexed).")
    parser.add_argument("--end-page", type=int, default=None, help="End page (inclusive).")
    return parser


def run_showcase(file_path: Path, out_dir: Path, start_page: int | None, end_page: int | None) -> int:
    file_path = file_path.resolve()
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    strategy = detect_strategy(file_path)
    result = extract_raw(file_path, start_page=start_page, end_page=end_page)

    if result.error:
        print(f"Error: {result.error}")
        return 1

    markdown = to_markdown(result, include_metadata=True)
    quality = text_quality_score(result.full_text)
    cid = cid_ratio(result.full_text)

    stem = file_path.stem
    md_path = out_dir / f"{stem}.extracted.md"
    json_path = out_dir / f"{stem}.report.json"

    md_path.write_text(markdown, encoding="utf-8")

    report: dict[str, Any] = {
        "source": str(file_path),
        "detected_strategy": strategy,
        "backend_used": result.backend_used,
        "pages": result.total_pages,
        "total_chars": result.total_chars,
        "estimated_tokens": result.estimated_tokens,
        "text_quality_score": round(quality, 4),
        "cid_ratio": round(cid, 4),
        "output_markdown": str(md_path),
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Showcase complete")
    print(f"- Strategy: {strategy}")
    print(f"- Backend: {result.backend_used}")
    print(f"- Pages: {result.total_pages}")
    print(f"- Estimated tokens: {result.estimated_tokens}")
    print(f"- Quality score: {quality:.2%}")
    print(f"- Markdown: {md_path}")
    print(f"- Report JSON: {json_path}")
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(
        run_showcase(
            file_path=args.file,
            out_dir=args.out,
            start_page=args.start_page,
            end_page=args.end_page,
        )
    )


if __name__ == "__main__":
    main()