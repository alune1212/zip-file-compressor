# ZIP Compressor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python CLI that extracts a ZIP archive, recursively compresses supported PDF/JPG/JPEG/PNG files toward a per-file size limit, preserves directory structure, and writes a new ZIP plus logs and summary output.

**Architecture:** The implementation centers on a small pipeline module that orchestrates archive extraction, recursive scanning, per-file processing, reporting, and re-packaging. File-type-specific behavior lives behind focused compressor modules so image and PDF handling remain isolated and testable while the CLI stays thin.

**Tech Stack:** Python 3.13+, standard library (`argparse`, `zipfile`, `pathlib`, `tempfile`, `shutil`, `logging`, `subprocess`, `dataclasses`, `enum`), Pillow, pytest

---

## File Map

### Application files

- Create: `main.py`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `zip_compressor/__init__.py`
- Create: `zip_compressor/__main__.py`
- Create: `zip_compressor/models.py`
- Create: `zip_compressor/archive.py`
- Create: `zip_compressor/scanner.py`
- Create: `zip_compressor/reporter.py`
- Create: `zip_compressor/pipeline.py`
- Create: `zip_compressor/compressors/__init__.py`
- Create: `zip_compressor/compressors/image_compressor.py`
- Create: `zip_compressor/compressors/pdf_compressor.py`

### Test files

- Create: `tests/test_models.py`
- Create: `tests/test_scanner.py`
- Create: `tests/test_archive.py`
- Create: `tests/test_reporter.py`
- Create: `tests/test_image_compressor.py`
- Create: `tests/test_pdf_compressor.py`
- Create: `tests/test_pipeline.py`
- Create: `tests/test_cli.py`

## Task 1: Scaffold the package, dependencies, and shared data models

**Files:**
- Create: `requirements.txt`
- Create: `zip_compressor/__init__.py`
- Create: `zip_compressor/__main__.py`
- Create: `zip_compressor/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from pathlib import Path

from zip_compressor.models import (
    CompressionConfig,
    FailureReason,
    FileCategory,
    FileProcessResult,
    FileStatus,
)


def test_default_config_uses_expected_limits(tmp_path: Path) -> None:
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip")
    assert config.max_size_kb == 2000
    assert config.png_allow_jpg is False
    assert config.pdf_strategy == "none"
    assert config.min_jpeg_quality == 35


def test_file_process_result_reports_target_match() -> None:
    result = FileProcessResult(
        relative_path=Path("nested/photo.jpg"),
        category=FileCategory.JPEG,
        status=FileStatus.COMPRESSED_TO_TARGET,
        original_size_bytes=4_000_000,
        final_size_bytes=1_500_000,
        failure_reason=None,
        message="compressed",
    )
    assert result.reached_target is True
    assert result.was_skipped is False


def test_file_process_result_flags_failures() -> None:
    result = FileProcessResult(
        relative_path=Path("broken.pdf"),
        category=FileCategory.PDF,
        status=FileStatus.FAILED,
        original_size_bytes=3_500_000,
        final_size_bytes=None,
        failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
        message="ghostscript missing",
    )
    assert result.reached_target is False
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL because `zip_compressor.models` does not exist yet.

- [ ] **Step 3: Write the minimal package and model implementation**

`requirements.txt`

```text
Pillow>=11.0.0
pytest>=8.0.0
```

`zip_compressor/__init__.py`

```python
"""ZIP content compressor package."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

`zip_compressor/__main__.py`

```python
from .pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
```

`zip_compressor/models.py`

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class FileCategory(str, Enum):
    PDF = "pdf"
    JPEG = "jpeg"
    PNG = "png"
    UNSUPPORTED = "unsupported"


class FileStatus(str, Enum):
    ALREADY_WITHIN_TARGET = "already_within_target"
    COMPRESSED_TO_TARGET = "compressed_to_target"
    COMPRESSED_BUT_ABOVE_TARGET = "compressed_but_above_target"
    SKIPPED_UNSUPPORTED = "skipped_unsupported"
    FAILED = "failed"


class FailureReason(str, Enum):
    UNSUPPORTED_TYPE = "unsupported_type"
    CORRUPTED_FILE = "corrupted_file"
    IMAGE_OPEN_FAILED = "image_open_failed"
    IMAGE_SAVE_FAILED = "image_save_failed"
    IMAGE_CANNOT_REACH_TARGET = "image_cannot_reach_target"
    PDF_STRATEGY_UNAVAILABLE = "pdf_strategy_unavailable"
    PDF_COMPRESSION_FAILED = "pdf_compression_failed"
    ZIP_EXTRACT_ERROR = "zip_extract_error"
    ZIP_PACK_ERROR = "zip_pack_error"
    UNEXPECTED_ERROR = "unexpected_error"


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

    @property
    def max_size_bytes(self) -> int:
        return self.max_size_kb * 1024


@dataclass(slots=True)
class DiscoveredFile:
    absolute_path: Path
    relative_path: Path
    category: FileCategory
    size_bytes: int


@dataclass(slots=True)
class FileProcessResult:
    relative_path: Path
    category: FileCategory
    status: FileStatus
    original_size_bytes: int
    final_size_bytes: int | None
    failure_reason: FailureReason | None
    message: str

    @property
    def reached_target(self) -> bool:
        return self.status in {
            FileStatus.ALREADY_WITHIN_TARGET,
            FileStatus.COMPRESSED_TO_TARGET,
        }

    @property
    def was_skipped(self) -> bool:
        return self.status is FileStatus.SKIPPED_UNSUPPORTED
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit the scaffold and models**

```bash
git add requirements.txt zip_compressor/__init__.py zip_compressor/__main__.py zip_compressor/models.py tests/test_models.py
git commit -m "feat: add package scaffold and shared models"
```

## Task 2: Implement recursive scanning and file categorization

**Files:**
- Create: `zip_compressor/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Write the failing scanner tests**

```python
from pathlib import Path

from zip_compressor.models import FileCategory
from zip_compressor.scanner import categorize_file, scan_files


def test_categorize_file_is_case_insensitive() -> None:
    assert categorize_file(Path("Report.PDF")) is FileCategory.PDF
    assert categorize_file(Path("Photo.JPEG")) is FileCategory.JPEG
    assert categorize_file(Path("diagram.PnG")) is FileCategory.PNG
    assert categorize_file(Path("notes.txt")) is FileCategory.UNSUPPORTED


def test_scan_files_recurses_and_preserves_relative_paths(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    image_path = nested / "photo.jpg"
    text_path = tmp_path / "readme.md"
    image_path.write_bytes(b"jpeg-data")
    text_path.write_text("hello", encoding="utf-8")

    discovered = scan_files(tmp_path)

    assert [item.relative_path for item in discovered] == [Path("a/b/photo.jpg"), Path("readme.md")]
    assert discovered[0].category is FileCategory.JPEG
    assert discovered[1].category is FileCategory.UNSUPPORTED
```

- [ ] **Step 2: Run the scanner tests to verify they fail**

Run: `uv run pytest tests/test_scanner.py -v`
Expected: FAIL because `zip_compressor.scanner` does not exist yet.

- [ ] **Step 3: Write the minimal scanner implementation**

`zip_compressor/scanner.py`

```python
from pathlib import Path

from .models import DiscoveredFile, FileCategory


def categorize_file(path: Path) -> FileCategory:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return FileCategory.PDF
    if suffix in {".jpg", ".jpeg"}:
        return FileCategory.JPEG
    if suffix == ".png":
        return FileCategory.PNG
    return FileCategory.UNSUPPORTED


def scan_files(root_dir: Path) -> list[DiscoveredFile]:
    discovered: list[DiscoveredFile] = []
    for path in sorted(root_dir.rglob("*")):
        if not path.is_file():
            continue
        discovered.append(
            DiscoveredFile(
                absolute_path=path,
                relative_path=path.relative_to(root_dir),
                category=categorize_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return discovered
```

- [ ] **Step 4: Run the scanner tests to verify they pass**

Run: `uv run pytest tests/test_scanner.py -v`
Expected: PASS with 2 passing tests.

- [ ] **Step 5: Commit the scanner**

```bash
git add zip_compressor/scanner.py tests/test_scanner.py
git commit -m "feat: add recursive file scanner"
```

## Task 3: Add safe ZIP extraction and archive packaging

**Files:**
- Create: `zip_compressor/archive.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: Write the failing archive tests**

```python
import zipfile
from pathlib import Path

import pytest

from zip_compressor.archive import create_zip_from_directory, extract_zip_to_directory


def test_extract_zip_to_directory_restores_nested_files(tmp_path: Path) -> None:
    source_zip = tmp_path / "source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("nested/file.txt", "payload")

    destination = tmp_path / "out"
    extract_zip_to_directory(source_zip, destination)

    assert (destination / "nested" / "file.txt").read_text(encoding="utf-8") == "payload"


def test_extract_zip_to_directory_rejects_path_traversal(tmp_path: Path) -> None:
    source_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("../evil.txt", "bad")

    with pytest.raises(ValueError, match="Unsafe ZIP member path"):
        extract_zip_to_directory(source_zip, tmp_path / "out")


def test_create_zip_from_directory_preserves_relative_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    nested = root / "dir"
    nested.mkdir()
    (nested / "file.txt").write_text("ok", encoding="utf-8")
    output_zip = tmp_path / "result.zip"

    create_zip_from_directory(root, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        assert archive.namelist() == ["dir/file.txt"]
```

- [ ] **Step 2: Run the archive tests to verify they fail**

Run: `uv run pytest tests/test_archive.py -v`
Expected: FAIL because `zip_compressor.archive` does not exist yet.

- [ ] **Step 3: Write the minimal archive implementation**

`zip_compressor/archive.py`

```python
from pathlib import Path
import zipfile


def _validate_zip_member(member_name: str, destination_dir: Path) -> Path:
    target_path = destination_dir / member_name
    resolved_target = target_path.resolve()
    resolved_destination = destination_dir.resolve()
    if not str(resolved_target).startswith(str(resolved_destination)):
        raise ValueError(f"Unsafe ZIP member path: {member_name}")
    return target_path


def extract_zip_to_directory(source_zip: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip, "r") as archive:
        for member in archive.infolist():
            target_path = _validate_zip_member(member.filename, destination_dir)
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as input_handle, target_path.open("wb") as output_handle:
                output_handle.write(input_handle.read())


def create_zip_from_directory(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())
```

- [ ] **Step 4: Run the archive tests to verify they pass**

Run: `uv run pytest tests/test_archive.py -v`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit the archive utilities**

```bash
git add zip_compressor/archive.py tests/test_archive.py
git commit -m "feat: add safe zip extraction and packaging"
```

## Task 4: Add reporting and summary aggregation

**Files:**
- Create: `zip_compressor/reporter.py`
- Test: `tests/test_reporter.py`

- [ ] **Step 1: Write the failing reporter tests**

```python
from pathlib import Path

from zip_compressor.models import FailureReason, FileCategory, FileProcessResult, FileStatus
from zip_compressor.reporter import build_summary


def test_build_summary_counts_each_outcome() -> None:
    results = [
        FileProcessResult(Path("a.jpg"), FileCategory.JPEG, FileStatus.ALREADY_WITHIN_TARGET, 10, 10, None, "ok"),
        FileProcessResult(Path("b.png"), FileCategory.PNG, FileStatus.COMPRESSED_TO_TARGET, 100, 50, None, "ok"),
        FileProcessResult(
            Path("c.pdf"),
            FileCategory.PDF,
            FileStatus.FAILED,
            100,
            None,
            FailureReason.PDF_STRATEGY_UNAVAILABLE,
            "missing",
        ),
        FileProcessResult(
            Path("d.txt"),
            FileCategory.UNSUPPORTED,
            FileStatus.SKIPPED_UNSUPPORTED,
            20,
            20,
            FailureReason.UNSUPPORTED_TYPE,
            "skip",
        ),
    ]

    summary = build_summary(results)

    assert summary.total_files == 4
    assert summary.supported_files == 3
    assert summary.already_within_target == 1
    assert summary.compressed_to_target == 1
    assert summary.failed_files == 1
    assert summary.skipped_unsupported == 1
    assert summary.failures[0].relative_path == Path("c.pdf")
```

- [ ] **Step 2: Run the reporter tests to verify they fail**

Run: `uv run pytest tests/test_reporter.py -v`
Expected: FAIL because `build_summary` and `RunSummary` do not exist yet.

- [ ] **Step 3: Extend the models and implement reporter helpers**

Append to `zip_compressor/models.py`

```python
@dataclass(slots=True)
class RunSummary:
    total_files: int
    supported_files: int
    already_within_target: int
    compressed_to_target: int
    compressed_but_above_target: int
    skipped_unsupported: int
    failed_files: int
    failures: list[FileProcessResult]
```

`zip_compressor/reporter.py`

```python
import logging
from pathlib import Path

from .models import FileCategory, FileProcessResult, FileStatus, RunSummary


def configure_logging(log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", handlers=handlers, force=True)


def build_summary(results: list[FileProcessResult]) -> RunSummary:
    failures = [item for item in results if item.status is FileStatus.FAILED or item.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET]
    return RunSummary(
        total_files=len(results),
        supported_files=sum(1 for item in results if item.category is not FileCategory.UNSUPPORTED),
        already_within_target=sum(1 for item in results if item.status is FileStatus.ALREADY_WITHIN_TARGET),
        compressed_to_target=sum(1 for item in results if item.status is FileStatus.COMPRESSED_TO_TARGET),
        compressed_but_above_target=sum(1 for item in results if item.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET),
        skipped_unsupported=sum(1 for item in results if item.status is FileStatus.SKIPPED_UNSUPPORTED),
        failed_files=sum(1 for item in results if item.status is FileStatus.FAILED),
        failures=failures,
    )
```

- [ ] **Step 4: Run the reporter tests to verify they pass**

Run: `uv run pytest tests/test_reporter.py -v`
Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit the reporting layer**

```bash
git add zip_compressor/models.py zip_compressor/reporter.py tests/test_reporter.py
git commit -m "feat: add summary reporting"
```

## Task 5: Implement JPEG compression with iterative quality and scaling

**Files:**
- Create: `zip_compressor/compressors/__init__.py`
- Create: `zip_compressor/compressors/image_compressor.py`
- Test: `tests/test_image_compressor.py`

- [ ] **Step 1: Write the failing JPEG tests**

```python
from pathlib import Path

from PIL import Image

from zip_compressor.models import CompressionConfig, FileCategory, FileStatus
from zip_compressor.compressors.image_compressor import compress_image_file


def test_compress_image_file_skips_small_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "small.jpg"
    Image.new("RGB", (100, 100), color="red").save(image_path, format="JPEG", quality=70)
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip", max_size_kb=500)

    result = compress_image_file(image_path, Path("small.jpg"), FileCategory.JPEG, config)

    assert result.status is FileStatus.ALREADY_WITHIN_TARGET


def test_compress_image_file_reduces_large_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "large.jpg"
    Image.effect_noise((2400, 2400), 100).convert("RGB").save(image_path, format="JPEG", quality=95)
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        max_size_kb=500,
        min_image_side=600,
        min_jpeg_quality=35,
    )

    result = compress_image_file(image_path, Path("large.jpg"), FileCategory.JPEG, config)

    assert result.status in {FileStatus.COMPRESSED_TO_TARGET, FileStatus.COMPRESSED_BUT_ABOVE_TARGET}
    assert result.final_size_bytes is not None
    assert result.final_size_bytes < result.original_size_bytes
```

- [ ] **Step 2: Run the JPEG tests to verify they fail**

Run: `uv run pytest tests/test_image_compressor.py -v -k jpeg`
Expected: FAIL because the image compressor module does not exist yet.

- [ ] **Step 3: Write the minimal image compressor implementation for JPEG**

`zip_compressor/compressors/__init__.py`

```python
"""Compression backends."""
```

`zip_compressor/compressors/image_compressor.py`

```python
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ..models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus

JPEG_QUALITIES = [95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35]
SCALE_STEPS = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6]


def _save_jpeg_candidate(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


def compress_image_file(
    file_path: Path,
    relative_path: Path,
    category: FileCategory,
    config: CompressionConfig,
) -> FileProcessResult:
    original_size = file_path.stat().st_size
    if original_size <= config.max_size_bytes:
        return FileProcessResult(relative_path, category, FileStatus.ALREADY_WITHIN_TARGET, original_size, original_size, None, "already within target")

    try:
        with Image.open(file_path) as source:
            base_image = source.convert("RGB")
    except UnidentifiedImageError:
        return FileProcessResult(relative_path, category, FileStatus.FAILED, original_size, None, FailureReason.CORRUPTED_FILE, "cannot identify image")

    best_bytes: bytes | None = None
    best_size = original_size

    for scale in SCALE_STEPS:
        width = max(int(base_image.width * scale), config.min_image_side)
        height = max(int(base_image.height * scale), config.min_image_side)
        resized = base_image if scale == 1.0 else base_image.resize((width, height))
        for quality in [q for q in JPEG_QUALITIES if q >= config.min_jpeg_quality]:
            candidate = _save_jpeg_candidate(resized, quality)
            candidate_size = len(candidate)
            if candidate_size < best_size:
                best_size = candidate_size
                best_bytes = candidate
            if candidate_size <= config.max_size_bytes:
                file_path.write_bytes(candidate)
                return FileProcessResult(relative_path, category, FileStatus.COMPRESSED_TO_TARGET, original_size, candidate_size, None, f"compressed with scale={scale} quality={quality}")

    if best_bytes is not None:
        file_path.write_bytes(best_bytes)
        return FileProcessResult(
            relative_path,
            category,
            FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
            original_size,
            best_size,
            FailureReason.IMAGE_CANNOT_REACH_TARGET,
            "best effort JPEG compression did not reach target",
        )
    return FileProcessResult(relative_path, category, FileStatus.FAILED, original_size, None, FailureReason.IMAGE_SAVE_FAILED, "failed to save jpeg candidate")
```

- [ ] **Step 4: Run the JPEG tests to verify they pass**

Run: `uv run pytest tests/test_image_compressor.py -v -k jpeg`
Expected: PASS with the JPEG-focused tests green.

- [ ] **Step 5: Commit JPEG compression support**

```bash
git add zip_compressor/compressors/__init__.py zip_compressor/compressors/image_compressor.py tests/test_image_compressor.py
git commit -m "feat: add iterative jpeg compression"
```

## Task 6: Extend image compression for PNG optimization and optional JPG conversion

**Files:**
- Modify: `zip_compressor/compressors/image_compressor.py`
- Modify: `tests/test_image_compressor.py`

- [ ] **Step 1: Write the failing PNG tests**

Append to `tests/test_image_compressor.py`

```python
def test_compress_image_file_handles_png_without_format_change_by_default(tmp_path: Path) -> None:
    image_path = tmp_path / "large.png"
    Image.effect_noise((1800, 1800), 100).convert("RGBA").save(image_path, format="PNG")
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip", max_size_kb=300)

    result = compress_image_file(image_path, Path("large.png"), FileCategory.PNG, config)

    assert result.final_size_bytes is not None
    assert image_path.suffix.lower() == ".png"


def test_compress_image_file_can_convert_png_to_jpg_when_enabled(tmp_path: Path) -> None:
    image_path = tmp_path / "opaque.png"
    Image.effect_noise((1800, 1800), 100).convert("RGB").save(image_path, format="PNG")
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        max_size_kb=250,
        png_allow_jpg=True,
    )

    result = compress_image_file(image_path, Path("opaque.png"), FileCategory.PNG, config)

    assert result.final_size_bytes is not None
    assert image_path.exists() is False or image_path.suffix.lower() in {".png", ".jpg"}
```

- [ ] **Step 2: Run the PNG tests to verify they fail**

Run: `uv run pytest tests/test_image_compressor.py -v -k png`
Expected: FAIL because PNG handling is not implemented yet.

- [ ] **Step 3: Extend the image compressor with PNG logic**

Add to `zip_compressor/compressors/image_compressor.py`

```python
PNG_LEVELS = [9, 8, 7, 6]
PNG_COLORS = [256, 128, 64]


def _has_transparency(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    return image.info.get("transparency") is not None


def _save_png_candidate(image: Image.Image, compress_level: int, colors: int | None) -> bytes:
    buffer = BytesIO()
    candidate = image
    if colors is not None and image.mode not in {"1", "L", "P"}:
        candidate = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
    candidate.save(buffer, format="PNG", optimize=True, compress_level=compress_level)
    return buffer.getvalue()


def _compress_png(file_path: Path, relative_path: Path, original_size: int, config: CompressionConfig) -> FileProcessResult:
    with Image.open(file_path) as source:
        base_image = source.copy()

    best_bytes: bytes | None = None
    best_size = original_size

    for scale in SCALE_STEPS:
        width = max(int(base_image.width * scale), config.min_image_side)
        height = max(int(base_image.height * scale), config.min_image_side)
        resized = base_image if scale == 1.0 else base_image.resize((width, height))
        color_options = [None, *PNG_COLORS]
        for compress_level in PNG_LEVELS:
            for colors in color_options:
                candidate = _save_png_candidate(resized, compress_level, colors)
                candidate_size = len(candidate)
                if candidate_size < best_size:
                    best_size = candidate_size
                    best_bytes = candidate
                if candidate_size <= config.max_size_bytes:
                    file_path.write_bytes(candidate)
                    return FileProcessResult(relative_path, FileCategory.PNG, FileStatus.COMPRESSED_TO_TARGET, original_size, candidate_size, None, f"png optimized scale={scale} level={compress_level} colors={colors}")

    if config.png_allow_jpg and not _has_transparency(base_image):
        jpeg_bytes = _save_jpeg_candidate(base_image.convert("RGB"), quality=70)
        if len(jpeg_bytes) < best_size:
            new_path = file_path.with_suffix(".jpg")
            if file_path.exists():
                file_path.unlink()
            new_path.write_bytes(jpeg_bytes)
            return FileProcessResult(relative_path.with_suffix(".jpg"), FileCategory.PNG, FileStatus.COMPRESSED_TO_TARGET if len(jpeg_bytes) <= config.max_size_bytes else FileStatus.COMPRESSED_BUT_ABOVE_TARGET, original_size, len(jpeg_bytes), None if len(jpeg_bytes) <= config.max_size_bytes else FailureReason.IMAGE_CANNOT_REACH_TARGET, "png converted to jpeg")

    if best_bytes is not None:
        file_path.write_bytes(best_bytes)
        return FileProcessResult(relative_path, FileCategory.PNG, FileStatus.COMPRESSED_BUT_ABOVE_TARGET, original_size, best_size, FailureReason.IMAGE_CANNOT_REACH_TARGET, "best effort PNG compression did not reach target")

    return FileProcessResult(relative_path, FileCategory.PNG, FileStatus.FAILED, original_size, None, FailureReason.IMAGE_SAVE_FAILED, "failed to save png candidate")
```

Update `compress_image_file()` to dispatch:

```python
    if category is FileCategory.PNG:
        return _compress_png(file_path, relative_path, original_size, config)
```

- [ ] **Step 4: Run the full image compressor tests to verify they pass**

Run: `uv run pytest tests/test_image_compressor.py -v`
Expected: PASS with both JPEG and PNG tests green.

- [ ] **Step 5: Commit the PNG support**

```bash
git add zip_compressor/compressors/image_compressor.py tests/test_image_compressor.py
git commit -m "feat: add png optimization workflow"
```

## Task 7: Add PDF compression strategy interface and Ghostscript detection

**Files:**
- Create: `zip_compressor/compressors/pdf_compressor.py`
- Test: `tests/test_pdf_compressor.py`

- [ ] **Step 1: Write the failing PDF tests**

```python
from pathlib import Path

from zip_compressor.compressors.pdf_compressor import build_pdf_compressor
from zip_compressor.models import CompressionConfig, FailureReason, FileCategory, FileStatus


def test_build_pdf_compressor_defaults_to_noop(tmp_path: Path) -> None:
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip")
    compressor = build_pdf_compressor(config)
    assert compressor.__class__.__name__ == "NoopPdfCompressor"


def test_noop_pdf_compressor_marks_file_as_unavailable(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip")

    compressor = build_pdf_compressor(config)
    result = compressor.compress(pdf_path, Path("sample.pdf"))

    assert result.category is FileCategory.PDF
    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE
```

- [ ] **Step 2: Run the PDF tests to verify they fail**

Run: `uv run pytest tests/test_pdf_compressor.py -v`
Expected: FAIL because the PDF compressor module does not exist yet.

- [ ] **Step 3: Implement the PDF strategy module**

`zip_compressor/compressors/pdf_compressor.py`

```python
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from ..models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus


@dataclass(slots=True)
class NoopPdfCompressor:
    config: CompressionConfig

    def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
        original_size = file_path.stat().st_size
        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PDF,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
            message="No PDF compression strategy is enabled.",
        )


@dataclass(slots=True)
class GhostscriptPdfCompressor:
    config: CompressionConfig
    executable: str

    def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
        original_size = file_path.stat().st_size
        if original_size <= self.config.max_size_bytes:
            return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.ALREADY_WITHIN_TARGET, original_size, original_size, None, "already within target")
        settings = ["/printer", "/ebook", "/screen"]
        best_size = original_size
        best_output: bytes | None = None
        for setting in settings:
            candidate_path = file_path.with_suffix(".candidate.pdf")
            command = [
                self.executable,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={setting}",
                "-dNOPAUSE",
                "-dBATCH",
                "-dQUIET",
                f"-sOutputFile={candidate_path}",
                str(file_path),
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.FAILED, original_size, None, FailureReason.PDF_COMPRESSION_FAILED, exc.stderr.strip() or "ghostscript failed")
            candidate_size = candidate_path.stat().st_size
            candidate_bytes = candidate_path.read_bytes()
            candidate_path.unlink(missing_ok=True)
            if candidate_size < best_size:
                best_size = candidate_size
                best_output = candidate_bytes
            if candidate_size <= self.config.max_size_bytes:
                file_path.write_bytes(candidate_bytes)
                return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.COMPRESSED_TO_TARGET, original_size, candidate_size, None, f"compressed with {setting}")
        if best_output is not None:
            file_path.write_bytes(best_output)
            return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.COMPRESSED_BUT_ABOVE_TARGET, original_size, best_size, FailureReason.PDF_COMPRESSION_FAILED, "best effort PDF compression did not reach target")
        return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.FAILED, original_size, None, FailureReason.PDF_COMPRESSION_FAILED, "no PDF output produced")


def detect_ghostscript() -> str | None:
    for command in ("gswin64c", "gswin32c", "gs"):
        if shutil.which(command):
            return command
    return None


def build_pdf_compressor(config: CompressionConfig) -> NoopPdfCompressor | GhostscriptPdfCompressor:
    if config.pdf_strategy != "ghostscript":
        return NoopPdfCompressor(config)
    executable = detect_ghostscript()
    if executable is None:
        return NoopPdfCompressor(config)
    return GhostscriptPdfCompressor(config, executable)
```

- [ ] **Step 4: Run the PDF tests to verify they pass**

Run: `uv run pytest tests/test_pdf_compressor.py -v`
Expected: PASS with 2 passing tests.

- [ ] **Step 5: Commit the PDF strategy layer**

```bash
git add zip_compressor/compressors/pdf_compressor.py tests/test_pdf_compressor.py
git commit -m "feat: add pluggable pdf compression strategies"
```

## Task 8: Build the main pipeline with per-file dispatch and resilient error handling

**Files:**
- Create: `zip_compressor/pipeline.py`
- Modify: `zip_compressor/models.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing pipeline tests**

```python
import zipfile
from pathlib import Path

from PIL import Image

from zip_compressor.models import CompressionConfig
from zip_compressor.pipeline import run_pipeline


def test_run_pipeline_processes_zip_and_writes_output_archive(tmp_path: Path) -> None:
    input_zip = tmp_path / "input.zip"
    with zipfile.ZipFile(input_zip, "w") as archive:
        image_path = tmp_path / "source.jpg"
        Image.new("RGB", (200, 200), color="blue").save(image_path, format="JPEG", quality=70)
        archive.write(image_path, "nested/photo.jpg")
        archive.writestr("nested/readme.txt", "skip me")

    output_zip = tmp_path / "output.zip"
    config = CompressionConfig(input_zip=input_zip, output_zip=output_zip, max_size_kb=500)

    pipeline_result = run_pipeline(config)

    assert output_zip.exists()
    assert pipeline_result.summary.total_files == 2
    with zipfile.ZipFile(output_zip) as archive:
        assert sorted(archive.namelist()) == ["nested/photo.jpg", "nested/readme.txt"]
```

- [ ] **Step 2: Run the pipeline tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL because `run_pipeline` does not exist yet.

- [ ] **Step 3: Extend shared models with a run result and implement the pipeline**

Append to `zip_compressor/models.py`

```python
@dataclass(slots=True)
class PipelineResult:
    summary: RunSummary
    results: list[FileProcessResult]
```

`zip_compressor/pipeline.py`

```python
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from .archive import create_zip_from_directory, extract_zip_to_directory
from .compressors.image_compressor import compress_image_file
from .compressors.pdf_compressor import build_pdf_compressor
from .models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus, PipelineResult
from .reporter import build_summary
from .scanner import scan_files


def run_pipeline(config: CompressionConfig) -> PipelineResult:
    results: list[FileProcessResult] = []
    pdf_compressor = build_pdf_compressor(config)

    with TemporaryDirectory(prefix="zip-compressor-") as temp_dir:
        working_dir = Path(temp_dir)
        extract_zip_to_directory(config.input_zip, working_dir)

        for discovered in scan_files(working_dir):
            logging.info("Processing %s", discovered.relative_path.as_posix())
            if discovered.category is FileCategory.UNSUPPORTED:
                results.append(
                    FileProcessResult(
                        relative_path=discovered.relative_path,
                        category=discovered.category,
                        status=FileStatus.SKIPPED_UNSUPPORTED,
                        original_size_bytes=discovered.size_bytes,
                        final_size_bytes=discovered.size_bytes,
                        failure_reason=FailureReason.UNSUPPORTED_TYPE,
                        message="unsupported file type",
                    )
                )
                continue

            try:
                if discovered.category in {FileCategory.JPEG, FileCategory.PNG}:
                    result = compress_image_file(discovered.absolute_path, discovered.relative_path, discovered.category, config)
                else:
                    result = pdf_compressor.compress(discovered.absolute_path, discovered.relative_path)
                results.append(result)
            except Exception as exc:
                results.append(
                    FileProcessResult(
                        relative_path=discovered.relative_path,
                        category=discovered.category,
                        status=FileStatus.FAILED,
                        original_size_bytes=discovered.size_bytes,
                        final_size_bytes=None,
                        failure_reason=FailureReason.UNEXPECTED_ERROR,
                        message=str(exc),
                    )
                )

        create_zip_from_directory(working_dir, config.output_zip)

    summary = build_summary(results)
    return PipelineResult(summary=summary, results=results)
```

- [ ] **Step 4: Run the pipeline tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS with the pipeline integration test green.

- [ ] **Step 5: Commit the processing pipeline**

```bash
git add zip_compressor/models.py zip_compressor/pipeline.py tests/test_pipeline.py
git commit -m "feat: add archive processing pipeline"
```

## Task 9: Add CLI entry points, summary output, and user documentation

**Files:**
- Create: `main.py`
- Modify: `zip_compressor/__main__.py`
- Modify: `zip_compressor/pipeline.py`
- Create: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
from pathlib import Path

from zip_compressor.pipeline import build_argument_parser


def test_build_argument_parser_uses_expected_defaults() -> None:
    parser = build_argument_parser()
    args = parser.parse_args(["--input", "in.zip", "--output", "out.zip"])
    assert args.max_size_kb == 2000
    assert args.pdf_strategy == "none"
    assert args.png_allow_jpg is False
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL because the CLI parser does not exist yet.

- [ ] **Step 3: Implement the CLI and README**

Add to `zip_compressor/pipeline.py`

```python
import argparse

from .reporter import configure_logging


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compress supported files inside a ZIP archive.")
    parser.add_argument("--input", required=True, dest="input_zip", type=Path)
    parser.add_argument("--output", required=True, dest="output_zip", type=Path)
    parser.add_argument("--max-size-kb", type=int, default=2000)
    parser.add_argument("--png-allow-jpg", action="store_true")
    parser.add_argument("--pdf-strategy", choices=["none", "ghostscript"], default="none")
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--min-image-side", type=int, default=800)
    parser.add_argument("--min-jpeg-quality", type=int, default=35)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    config = CompressionConfig(
        input_zip=args.input_zip,
        output_zip=args.output_zip,
        max_size_kb=args.max_size_kb,
        png_allow_jpg=args.png_allow_jpg,
        pdf_strategy=args.pdf_strategy,
        log_file=args.log_file,
        min_image_side=args.min_image_side,
        min_jpeg_quality=args.min_jpeg_quality,
    )
    configure_logging(config.log_file)
    pipeline_result = run_pipeline(config)
    logging.info("Total files: %s", pipeline_result.summary.total_files)
    logging.info("Compressed to target: %s", pipeline_result.summary.compressed_to_target)
    logging.info("Already within target: %s", pipeline_result.summary.already_within_target)
    logging.info("Failed files: %s", pipeline_result.summary.failed_files)
    for failure in pipeline_result.summary.failures:
        logging.info("Failure: %s -> %s", failure.relative_path.as_posix(), failure.message)
    return 0 if pipeline_result.summary.failed_files == 0 else 1
```

`main.py`

```python
from zip_compressor.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
```

`README.md`

````markdown
# ZIP File Compressor

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python main.py --input input.zip --output output.zip --max-size-kb 2000
python -m zip_compressor --input input.zip --output output.zip --max-size-kb 2000
```

## Ghostscript on Windows

1. Download and install Ghostscript from the official installer.
2. Make sure `gswin64c.exe` or `gswin32c.exe` is on `PATH`.
3. Verify with:

```powershell
gswin64c -version
```
````

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS with the parser default test green.

- [ ] **Step 5: Commit the CLI and docs**

```bash
git add main.py zip_compressor/pipeline.py zip_compressor/__main__.py README.md tests/test_cli.py
git commit -m "feat: add cli entry point and usage docs"
```

## Task 10: Run the full test suite and polish any mismatches

**Files:**
- Modify: any file touched above if tests expose gaps
- Test: `tests/test_models.py`
- Test: `tests/test_scanner.py`
- Test: `tests/test_archive.py`
- Test: `tests/test_reporter.py`
- Test: `tests/test_image_compressor.py`
- Test: `tests/test_pdf_compressor.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Run the complete suite**

Run: `uv run pytest -v`
Expected: PASS with all planned tests green.

- [ ] **Step 2: Patch any failing mismatches**

If failures show naming drift or missing imports, fix them immediately in place. Keep the fixes minimal and consistent with earlier tasks. Common corrections expected here:

```python
from zip_compressor.compressors.image_compressor import compress_image_file
```

```python
failure_reason=FailureReason.PDF_COMPRESSION_FAILED
```

- [ ] **Step 3: Re-run the full suite**

Run: `uv run pytest -v`
Expected: PASS with no failures.

- [ ] **Step 4: Manually smoke-test the CLI**

Run: `python main.py --help`
Expected: usage text showing `--input`, `--output`, `--max-size-kb`, `--png-allow-jpg`, and `--pdf-strategy`.

- [ ] **Step 5: Commit the verification and polish**

```bash
git add .
git commit -m "test: verify zip compressor end to end"
```

## Self-Review

### Spec coverage

- ZIP extraction, recursive scanning, preserving directory structure: covered by Tasks 2, 3, and 8.
- JPEG and PNG compression with iterative attempts: covered by Tasks 5 and 6.
- PDF strategy interface with optional Ghostscript: covered by Task 7.
- Logging and summary output: covered by Tasks 4 and 9.
- CLI shape and usage docs: covered by Task 9.
- Tests and final verification: covered by Task 10.

### Placeholder scan

- No placeholder markers remain.
- Each task has explicit files, concrete test names, run commands, and code blocks.

### Type consistency

- Shared names are consistent across tasks:
  - `CompressionConfig`
  - `FileCategory`
  - `FileStatus`
  - `FailureReason`
  - `FileProcessResult`
  - `RunSummary`
  - `PipelineResult`
  - `compress_image_file`
  - `build_pdf_compressor`
  - `run_pipeline`
  - `build_argument_parser`
  - `main`
