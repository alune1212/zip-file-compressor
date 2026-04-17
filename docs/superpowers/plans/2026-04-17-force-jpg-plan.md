# Force JPG Output Format - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--force-jpg` CLI flag that converts all PNG/PDF/JPEG files to JPEG format after compression.

**Architecture:** Add `force_jpg` config flag. When enabled, PNG images are always converted to JPEG, and PDF files are converted to multiple JPEG files (one per page). JPEG files remain as JPEG.

**Tech Stack:** Python, Pillow, Ghostscript (existing), existing project structure.

---

## Task 1: Add `force_jpg` to CompressionConfig

**Files:**
- Modify: `zip_compressor/models.py`

- [ ] **Step 1: Add `force_jpg` field to CompressionConfig**

Find the `CompressionConfig` dataclass and add `force_jpg: bool = False` after `min_jpeg_quality`:

```python
@dataclass(slots=True)
class CompressionConfig:
    input_zip: Path
    output_zip: Path
    max_size_kb: int = 2000
    png_allow_jpg: bool = False
    pdf_strategy: str = "none"
    log_file: Path | None = None
    min_image_side: int = 800
    min_jpeg_quality: int = 35
    force_jpg: bool = False  # NEW
```

- [ ] **Step 2: Verify file still imports correctly**

Run: `PYTHONPATH=. uv run python -c "from zip_compressor.models import CompressionConfig; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add zip_compressor/models.py
git commit -m "feat: add force_jpg flag to CompressionConfig"
```

---

## Task 2: Add `--force-jpg` CLI Argument

**Files:**
- Modify: `zip_compressor/pipeline.py:63-73`

- [ ] **Step 1: Add `--force-jpg` argument to parser**

In `build_argument_parser()`, add after `--min-jpeg-quality`:

```python
parser.add_argument("--force-jpg", action="store_true")
```

- [ ] **Step 2: Pass `force_jpg` to CompressionConfig in `main()`**

In `main()` function, add `force_jpg=args.force_jpg` to the `CompressionConfig` constructor:

```python
config = CompressionConfig(
    input_zip=args.input_zip,
    output_zip=args.output_zip,
    max_size_kb=args.max_size_kb,
    png_allow_jpg=args.png_allow_jpg,
    pdf_strategy=args.pdf_strategy,
    log_file=args.log_file,
    min_image_side=args.min_image_side,
    min_jpeg_quality=args.min_jpeg_quality,
    force_jpg=args.force_jpg,  # NEW
)
```

- [ ] **Step 3: Verify CLI accepts new argument**

Run: `PYTHONPATH=. uv run python -m zip_compressor --help | grep force-jpg`
Expected: `--force-jpg` appears in help output

- [ ] **Step 4: Commit**

```bash
git add zip_compressor/pipeline.py
git commit -m "feat: add --force-jpg CLI argument"
```

---

## Task 3: Force PNG → JPG Conversion in Image Compressor

**Files:**
- Modify: `zip_compressor/compressors/image_compressor.py:35-71`

- [ ] **Step 1: Write failing test for force JPG PNG conversion**

Create test file `tests/test_image_compressor_force_jpg.py`:

```python
from pathlib import Path
from zip_compressor.compressors.image_compressor import compress_image_file
from zip_compressor.models import CompressionConfig, FileCategory

def test_png_force_jpg_conversion(tmp_path):
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        force_jpg=True,
    )
    # Create a simple PNG file (red 10x10 pixel)
    png_path = tmp_path / "test.png"
    # ... create PNG image ...
    result = compress_image_file(png_path, Path("test.png"), FileCategory.PNG, config)
    assert result.relative_path.suffix == ".jpg"
    assert not png_path.exists()
    assert (tmp_path / "test.jpg").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_image_compressor_force_jpg.py -v`
Expected: FAIL - `.jpg` assertion fails

- [ ] **Step 3: Modify `_compress_png` to handle `force_jpg=True`**

In `_compress_png()`, after checking `config.png_allow_jpg` and `_has_transparency`, add `force_jpg` handling. When `force_jpg=True`, skip transparency check and always convert to JPG:

```python
if config.force_jpg:
    # Always convert to JPG, ignoring transparency
    jpeg_bytes = _save_jpeg_candidate(base_image.convert("RGB"), quality=70)
    if len(jpeg_bytes) < best_size:
        new_path = file_path.with_suffix(".jpg")
        if file_path.exists():
            file_path.unlink()
        new_path.write_bytes(jpeg_bytes)
        return FileProcessResult(relative_path.with_suffix(".jpg"), FileCategory.PNG, FileStatus.COMPRESSED_TO_TARGET if len(jpeg_bytes) <= config.max_size_bytes else FileStatus.COMPRESSED_BUT_ABOVE_TARGET, original_size, len(jpeg_bytes), None if len(jpeg_bytes) <= config.max_size_bytes else FailureReason.IMAGE_CANNOT_REACH_TARGET, "png converted to jpg (force-jpg)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_image_compressor_force_jpg.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zip_compressor/compressors/image_compressor.py tests/test_image_compressor_force_jpg.py
git commit -m "feat: force PNG to JPG conversion when force_jpg=True"
```

---

## Task 4: Add PDF → JPG Conversion (Multi-Page)

**Files:**
- Modify: `zip_compressor/compressors/pdf_compressor.py`

**Approach:** Use Ghostscript to render PDF pages to JPEG images. Ghostscript command:
```
gs -dNOPAUSE -dBATCH -sDEVICE=jpeg -r150 -dJPEGQ=85 -sOutputFile=output_%d.jpg input.pdf
```

- [ ] **Step 1: Write failing test for PDF multi-page conversion**

Create test file `tests/test_pdf_compressor_force_jpg.py`:

```python
from pathlib import Path
from zip_compressor.compressors.pdf_compressor import GhostscriptPdfCompressor, build_pdf_compressor
from zip_compressor.models import CompressionConfig, FileCategory, FileStatus

def test_pdf_force_jpg_converts_to_multiple_jpgs(tmp_path):
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        pdf_strategy="ghostscript",
        force_jpg=True,
        max_size_kb=2000,
    )
    # This test requires ghostscript and a real PDF
    # Skip if ghostscript not available
    compressor = build_pdf_compressor(config)
    if not isinstance(compressor, GhostscriptPdfCompressor):
        pytest.skip("ghostscript not available")
    # ... create test PDF and verify multi-page JPG output ...
```

- [ ] **Step 2: Add `force_jpg` parameter to `GhostscriptPdfCompressor.compress()`**

Modify `GhostscriptPdfCompressor` to add `force_jpg` handling. When `force_jpg=True`, use Ghostscript to render each page as JPG instead of compressing PDF:

```python
def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
    original_size = file_path.stat().st_size

    if self.config.force_jpg:
        # Convert PDF pages to JPG files
        output_pattern = file_path.with_suffix("_page_%d.jpg")
        command = [
            self.executable,
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=jpeg",
            "-r150",
            "-dJPEGQ=85",
            f"-sOutputFile={output_pattern}",
            str(file_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.FAILED, original_size, None, FailureReason.PDF_COMPRESSION_FAILED, "ghostscript failed to render PDF to JPG")

        # Find generated JPG files
        base_name = file_path.stem
        jpg_files = sorted(file_path.parent.glob(f"{base_name}_page_*.jpg"))
        if not jpg_files:
            return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.FAILED, original_size, None, FailureReason.PDF_COMPRESSION_FAILED, "no JPG files generated from PDF")

        # Delete original PDF
        file_path.unlink(missing_ok=True)

        # Report result for first page, track total pages
        first_jpg = jpg_files[0]
        total_size = sum(f.stat().st_size for f in jpg_files)
        return FileProcessResult(
            relative_path=first_jpg.relative_to(file_path.parent),
            category=FileCategory.PDF,
            status=FileStatus.COMPRESSED_TO_TARGET if total_size <= self.config.max_size_bytes else FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
            original_size_bytes=original_size,
            final_size_bytes=total_size,
            failure_reason=None if total_size <= self.config.max_size_bytes else FailureReason.PDF_COMPRESSION_FAILED,
            message=f"PDF converted to {len(jpg_files)} JPG pages",
        )

    # Original PDF compression logic continues below...
```

- [ ] **Step 3: Run test to verify it works**

Run: `PYTHONPATH=. uv run pytest tests/test_pdf_compressor_force_jpg.py -v`
Expected: PASS (or SKIP if ghostscript not available)

- [ ] **Step 4: Commit**

```bash
git add zip_compressor/compressors/pdf_compressor.py tests/test_pdf_compressor_force_jpg.py
git commit -m "feat: add PDF to JPG multi-page conversion when force_jpg=True"
```

---

## Task 5: Integration Test

**Files:**
- Modify: `tests/` (new integration test)

- [ ] **Step 1: Write integration test for force-jpg end-to-end**

Create `tests/test_force_jpg_integration.py`:

```python
from pathlib import Path
import zipfile
from zip_compressor.pipeline import run_pipeline
from zip_compressor.models import CompressionConfig

def test_force_jpg_end_to_end(tmp_path):
    # Create test ZIP with PNG and PDF files
    input_zip = tmp_path / "input.zip"
    output_zip = tmp_path / "output.zip"

    with zipfile.ZipFile(input_zip, 'w') as zf:
        # Add test PNG
        # Add test PDF
        pass

    config = CompressionConfig(
        input_zip=input_zip,
        output_zip=output_zip,
        force_jpg=True,
        max_size_kb=2000,
    )

    result = run_pipeline(config)

    # Verify output ZIP contains only .jpg files for converted images
    with zipfile.ZipFile(output_zip, 'r') as zf:
        names = zf.namelist()
        # All image and PDF files should be .jpg
        for name in names:
            if name.endswith(('.png', '.pdf')):
                assert False, f"Found non-JPG file: {name}"
```

- [ ] **Step 2: Run integration test**

Run: `PYTHONPATH=. uv run pytest tests/test_force_jpg_integration.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/test_force_jpg_integration.py
git commit -m "test: add force-jpg integration test"
```

---

## Self-Review Checklist

- [ ] All spec requirements covered: `force_jpg` flag, PNG→JPG, PDF→JPG (multi-page)
- [ ] No TBD/TODO placeholders in code
- [ ] Types consistent: `CompressionConfig.force_jpg: bool`
- [ ] CLI argument `--force-jpg` matches spec
- [ ] Tests written before implementation (TDD approach)
