# ZIP File Compressor

A local CLI tool that extracts a ZIP archive, recursively compresses supported PDF/JPG/JPEG/PNG files toward a per-file size limit, preserves directory structure, and writes a new ZIP with logs and summary output.

## Features

- **Recursive scanning** - Discovers all supported files in nested directories
- **JPEG compression** - Iterative quality and scaling to meet target size
- **PNG optimization** - Compression level and color palette reduction
- **PNG to JPEG conversion** - Optional conversion for opaque PNGs
- **PDF compression** - Ghostscript-based strategy (optional)
- **Path traversal protection** - Safe extraction of untrusted ZIP files
- **Summary reporting** - Per-file status and failure details

## Install

```bash
# Clone the repository
git clone https://github.com/alune1212/zip-file-compressor.git
cd zip-file-compressor

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
# Basic usage
python main.py --input input.zip --output output.zip

# With custom size limit (in KB)
python main.py --input input.zip --output output.zip --max-size-kb 1500

# Enable PNG to JPEG conversion for opaque images
python main.py --input input.zip --output output.zip --png-allow-jpg

# Enable PDF compression (requires Ghostscript)
python main.py --input input.zip --output output.zip --pdf-strategy ghostscript

# Save log to file
python main.py --input input.zip --output output.zip --log-file compressor.log

# Module execution
python -m zip_compressor --input input.zip --output output.zip
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | (required) | Input ZIP file path |
| `--output` | (required) | Output ZIP file path |
| `--max-size-kb` | 2000 | Target max file size in KB |
| `--png-allow-jpg` | False | Convert opaque PNGs to JPEG |
| `--pdf-strategy` | none | PDF compression: `none` or `ghostscript` |
| `--log-file` | None | Log file path |
| `--min-image-side` | 800 | Minimum image dimension in pixels |
| `--min-jpeg-quality` | 35 | Minimum JPEG quality (1-100) |

## Requirements

- Python 3.9+
- Pillow

### PDF Compression (Optional)

**macOS/Linux:**
```bash
# Install via Homebrew
brew install ghostscript

# Verify
gs -version
```

**Windows:**
1. Download Ghostscript from https://www.ghostscript.com/download/gsdnld.html
2. Install and add `gswin64c.exe` to PATH
3. Verify:
```powershell
gswin64c -version
```

## Project Structure

```
zip_compressor/
├── __init__.py          # Package entry
├── __main__.py          # Module entry point
├── models.py             # Data models (CompressionConfig, FileProcessResult, etc.)
├── scanner.py            # Recursive file discovery and categorization
├── archive.py            # ZIP extraction and packaging
├── reporter.py           # Summary aggregation and logging
├── pipeline.py           # Main orchestration and CLI
└── compressors/
    ├── __init__.py
    ├── image_compressor.py  # JPEG/PNG compression logic
    └── pdf_compressor.py    # PDF strategy interface
```

## Exit Codes

- `0` - Success (all files processed without failures)
- `1` - Partial success (some files failed or above target)

## License

MIT