# Text Extractor

[![PyPI version](https://img.shields.io/pypi/v/text-extractor-lightweight.svg)](https://pypi.org/project/text-extractor-lightweight/)
[![Python](https://img.shields.io/pypi/pyversions/text-extractor-lightweight.svg)](https://pypi.org/project/text-extractor-lightweight/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Lightweight MCP server + CLI for extracting text from PDFs and images, designed for agent workflows.

It is fast on normal digital PDFs, but can still recover text from difficult documents with quality-aware fallback and optional OCR.

## Features

- Zero-config extraction for standard PDFs
- Smart fallback chain for low-quality or scanned pages
- Optional OCR stack for image-heavy PDFs and image files
- MCP tools ready for VS Code, Claude, and agent runtimes
- CLI and Python API in one package

## Install

Install the package:

```bash
pip install text-extractor-lightweight
```

Optional extras:

```bash
# Fast extraction via PyMuPDF (recommended — handles complex fonts, 10-20x faster)
pip install "text-extractor-lightweight[fast]"

# OCR support (scanned PDFs, images)
pip install "text-extractor-lightweight[ocr]"

# Better handling of complex layouts
pip install "text-extractor-lightweight[docling]"

# Everything
pip install "text-extractor-lightweight[all]"
```

System dependencies for OCR:

- Tesseract OCR: https://github.com/tesseract-ocr/tesseract
- Poppler (`pdftoppm`) for PDF to image conversion

Windows (winget):

```powershell
winget install --id tesseract-ocr.tesseract -e
winget install --id oschwartz10612.Poppler -e
```

## CLI

The package name is `text-extractor-lightweight`, and it installs CLI commands `text-extractor` and `text-extractor-mcp`.

```bash
# Extract full text from a PDF
text-extractor report.pdf

# Extract from an image
text-extractor screenshot.png

# Extract only specific pages
text-extractor report.pdf --pages 1-5

# Show document metadata/summary only
text-extractor report.pdf --info

# Show which strategy would be used
text-extractor report.pdf --strategy

# Chunk large output by token budget
text-extractor large.pdf --chunk-tokens 50000
```

## MCP Server

Run directly with `uvx`:

```bash
uvx --from text-extractor-lightweight text-extractor-mcp
```

### Claude Code

```bash
claude mcp add text-extractor -- uvx --from text-extractor-lightweight text-extractor-mcp
```

### VS Code / GitHub Copilot

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "text-extractor": {
      "command": "uvx",
      "args": ["--from", "text-extractor-lightweight", "text-extractor-mcp"]
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "text-extractor": {
      "command": "uvx",
      "args": ["--from", "text-extractor-lightweight", "text-extractor-mcp"]
    }
  }
}
```

## Exposed MCP Tools

| Tool | Description |
|------|-------------|
| `extract_text_from_file` | Extract full text from a PDF or image as markdown |
| `extract_text_pages` | Extract text from a specific page range |
| `get_document_info` | Get page count, type, metadata, and token estimate |

## Extraction Strategy

Automatic routing selects the best backend by file type and quality:

```text
Image file        -> Tesseract OCR
Digital PDF       -> pymupdf (fast path, recommended)
                     pypdf (fallback if pymupdf not installed)
Garbled PDF text  -> pdfplumber -> docling (optional)
Scanned/image PDF -> pdf2image + Tesseract OCR
```

PDF fallback chain:

`pymupdf -> pdfplumber -> docling -> pdf2image+OCR`

PyMuPDF (`pip install "text-extractor-lightweight[fast]"`) is the preferred PDF backend. It correctly decodes custom embedded fonts (where pypdf/pdfplumber emit garbled `(cid:N)` output) and is 10–20x faster than pypdf.

## Python API

```python
from text_extractor.extract import extract_text, extract_raw

# Markdown output
markdown = extract_text("report.pdf")

# Structured output
result = extract_raw("report.pdf")
print(result.total_pages, result.estimated_tokens)
for page in result.pages:
    print(f"Page {page.page_number}: {page.char_count} chars")
```

## Troubleshooting

- If `text-extractor` is not found on Windows, ensure the Python Scripts directory is in PATH.
- For MCP stdio mode, do not send random JSON to stdin; only an MCP client should talk to the server.
- If OCR is not triggered on scanned docs, confirm Tesseract and Poppler are installed and visible to the process.

## Release

Quick publish flow:

```bash
python -m build
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

For the full step-by-step process, see `RELEASE_CHECKLIST.md`.

## License

MIT
