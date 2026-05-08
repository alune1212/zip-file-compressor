# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZIP File Compressor - A CLI tool that extracts ZIP archives, compresses PDF/JPG/JPEG/PNG files toward a per-file size limit, preserves directory structure, and outputs a new ZIP with logs and summary.

## Commands

```bash
# Install dependencies (creates .venv)
uv venv && uv pip install -r requirements.txt

# Run tests (2 PDF tests skip if ghostscript not installed)
.venv/bin/python -m pytest -q

# Alternative when uv cache is writable
PYTHONPATH=. uv run pytest -q

# Run single test file
PYTHONPATH=. uv run pytest tests/test_models.py -v

# Run CLI
PYTHONPATH=. uv run python main.py --input input.zip --output output.zip

# Or via module
PYTHONPATH=. uv run python -m zip_compressor --input input.zip --output output.zip
```

## Architecture

```
zip_compressor/
├── pipeline.py       # Main orchestration: CLI args, run_pipeline(), entry point
├── models.py        # Data models: CompressionConfig, FileProcessResult, RunSummary, enums
├── scanner.py       # Recursive file discovery, categorize_file()
├── archive.py       # ZIP extract/create with path traversal protection
├── reporter.py      # Logging config, build_summary()
└── compressors/
    ├── image_compressor.py  # JPEG/PNG compression with iterative quality/scaling
    └── pdf_compressor.py     # PDF strategy interface (Noop/Ghostscript)
```

**Processing Pipeline:**
1. Extract input ZIP to temp directory (with path traversal validation)
2. Recursively scan for PDF/JPG/JPEG/PNG files
3. Dispatch to image_compressor or pdf_compressor based on FileCategory
4. Re-package processed files to output ZIP
5. Build summary and log results

**Image Compression Strategy:**
- Iterates through scale factors (1.0 → 0.6) and JPEG quality levels (95 → 35)
- For PNG: compression levels (9→6) and color palette reduction (256→64)
- Optional PNG→JPEG conversion when `png_allow_jpg=True` and no transparency

**PDF Compression:**
- `NoopPdfCompressor` - Fails with `pdf_strategy_disabled` or `pdf_strategy_unavailable`
- `GhostscriptPdfCompressor` - Uses Ghostscript with /printer, /ebook, /screen settings (requires `gs` installed separately)
- Current live code uses Ghostscript `pdfwrite` for PDF compression only. Do not assume `--force-jpg` converts PDFs to JPG unless `zip_compressor/compressors/pdf_compressor.py` is changed and tested.

## Exit Codes

- `0` - Success (all files processed, no failures)
- `1` - Partial success (some files failed or exceeded target size)

## Key Types

- `FileCategory`: PDF, JPEG, PNG, UNSUPPORTED
- `FileStatus`: ALREADY_WITHIN_TARGET, COMPRESSED_TO_TARGET, COMPRESSED_BUT_ABOVE_TARGET, SKIPPED_UNSUPPORTED, FAILED (NOTE: `SUCCESS` does not exist)
- `FailureReason`: Various failure reasons for each operation type, including separate disabled/unavailable/cannot-reach-target PDF reasons
- `CompressionConfig`: All user-configurable parameters (max_size_kb, png_allow_jpg, force_jpg, pdf_strategy, min_image_side, min_jpeg_quality, etc.)
- `PipelineResult`: Contains `RunSummary` and list of `FileProcessResult` per file

## Gotchas

- **Ghostscript 为 PDF 压缩必需**: `gs` 必须单独安装 (macOS: `brew install ghostscript`)
- **PNG→JPEG 转换为有损转换**: 当 `png_allow_jpg=True` 时，透明度会被丢弃
- **`--force-jpg` 不是 all-JPG 保证**: 当前只强制 PNG 输出 JPG；PDF 仍需要 Ghostscript 压缩策略，已有 `.jpeg` 不会统一重命名为 `.jpg`。
- **本机交付 fallback 不属于仓库能力**: 2026-05-06/2026-05-08 曾用 macOS `/usr/bin/sips` 在仓库外把单页 PDF ZIP 转为全 JPG ZIP；这只是人工交付路径，代码里没有 `sips` fallback。
