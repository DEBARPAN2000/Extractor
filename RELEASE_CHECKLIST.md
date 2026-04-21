# Release Checklist (v0.2.0)

## 1. Pre-release sanity

- [ ] Confirm version is `0.2.0` in `pyproject.toml`.
- [ ] Confirm version is `0.2.0` in `src/text_extractor/__init__.py`.
- [ ] Run tests:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
py -m pytest -q
```

## 2. Build and validate package artifacts

```powershell
py -m pip install --upgrade build twine
py -m build
py -m twine check dist/*
```

Expected artifacts:

- `dist/text_extractor_lightweight-0.2.0.tar.gz`
- `dist/text_extractor_lightweight-0.2.0-py3-none-any.whl`

## 3. Publish to TestPyPI first

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "<testpypi-token>"
py -m twine upload --repository testpypi dist/*
```

Install verification from TestPyPI:

```powershell
py -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple text-extractor-lightweight==0.2.0
text-extractor --help
text-extractor-mcp
```

## 4. Publish to PyPI

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "<pypi-token>"
py -m twine upload dist/*
```

Production install verification:

```powershell
py -m pip install --upgrade text-extractor-lightweight==0.2.0
text-extractor --help
```

## 5. Git/tag/release

```powershell
git add README.md pyproject.toml src/text_extractor/__init__.py src/text_extractor/backends/__init__.py src/text_extractor/backends/docling_backend.py src/text_extractor/mcp_server.py src/text_extractor/router.py tests/test_router.py .gitignore RELEASE_CHECKLIST.md mcp-registry-payload.json

git commit -m "feat: phase 3 release with docling fallback"
git tag v0.2.0
git push origin main --follow-tags
```

## 6. MCP discoverability check

- [ ] Verify `uvx --from text-extractor-lightweight text-extractor-mcp` works.
- [ ] Verify tools visible in VS Code MCP integration.
- [ ] Submit MCP registry payload from `mcp-registry-payload.json`.
