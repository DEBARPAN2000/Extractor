# Text Extractor

Lightweight MCP server + CLI for extracting text from PDFs and images. Built for LLM agents.

**Zero-config** for digital PDFs. Quality-aware fallback and OCR support for scanned/image-heavy PDFs.

## Install

```bash
pip install text-extractor
```

For OCR support (scanned PDFs, images):

```bash
pip install text-extractor[ocr]
# Also install system dependencies:
# - Tesseract OCR: https://github.com/tesseract-ocr/tesseract
# - Poppler (pdftoppm) for PDF->image conversion
```

For high-quality extraction on complex layouts (optional):

```bash
pip install text-extractor[docling]
```

Windows (winget):

```powershell
winget install --id tesseract-ocr.tesseract -e
winget install --id oschwartz10612.Poppler -e
```

## CLI Usage

```bash
# Extract text from a PDF
text-extractor report.pdf

# Extract from an image
text-extractor screenshot.png

# Specific pages only
text-extractor report.pdf --pages 1-5

# Document info without full extraction
text-extractor report.pdf --info

# Check which strategy will be used
text-extractor report.pdf --strategy

# Large doc? Split into token-bounded chunks
text-extractor large.pdf --chunk-tokens 50000
```

## MCP Server — for AI Agents

### Claude Code

```bash
claude mcp add text-extractor -- uvx --from text-extractor text-extractor-mcp
```

### VS Code / GitHub Copilot

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "text-extractor": {
      "command": "uvx",
      "args": ["--from", "text-extractor", "text-extractor-mcp"]
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
      "args": ["--from", "text-extractor", "text-extractor-mcp"]
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `extract_text_from_file` | Extract full text from a PDF or image as markdown |
| `extract_text_pages` | Extract text from specific page range |
| `get_document_info` | Get page count, type, metadata, token estimate |

## How It Works

Smart routing picks the best backend automatically:

```
Image file       -> Tesseract OCR
Digital PDF      -> pypdf (fast)
Garbled PDF text -> pdfplumber (better font mapping)
Complex layout   -> docling (optional, higher fidelity)
Scanned/image PDF-> pdf2image + Tesseract OCR
```

Fallback chain for PDFs: `pypdf -> pdfplumber -> docling -> pdf2image+OCR`.

Performance features:

- In-memory extraction cache by file fingerprint (`path + size + mtime`)
- Page-range extraction (`extract_text_pages`) avoids parsing full documents
- Parallel OCR across pages
- Fast pre-sampling to detect low-quality extraction and skip wasteful paths on large PDFs

## Python API

```python
from text_extractor.extract import extract_text, extract_raw

# Get markdown string
markdown = extract_text("report.pdf")

# Get structured result
result = extract_raw("report.pdf")
print(result.total_pages, result.estimated_tokens)
for page in result.pages:
    print(f"Page {page.page_number}: {page.char_count} chars")
```

## License

MIT

## Release & Publishing

```bash
# Build artifacts
python -m build

# Publish to TestPyPI (recommended first)
python -m twine upload --repository testpypi dist/*

# Publish to PyPI
python -m twine upload dist/*
```

MCP Registry listing:

1. Ensure package is published and installable via `uvx --from text-extractor text-extractor-mcp`.
2. Submit tool metadata in MCP Registry format using this project's MCP server entry point.
3. Verify discovery in Claude/Copilot by adding server config shown above.
