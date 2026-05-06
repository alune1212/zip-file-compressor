import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.compressors.image_compressor import compress_image_file
from zip_compressor.models import CompressionConfig, FailureReason, FileCategory, FileStatus


def _build_config(tmp_path: Path, *, max_size_kb: int, min_image_side: int = 800) -> CompressionConfig:
    return CompressionConfig(
        input_zip=tmp_path / "input.zip",
        output_zip=tmp_path / "output.zip",
        max_size_kb=max_size_kb,
        min_image_side=min_image_side,
        min_jpeg_quality=35,
    )


def _write_jpeg(
    path: Path,
    *,
    size: tuple[int, int],
    quality: int = 95,
    progressive: bool = False,
) -> int:
    image = Image.effect_noise(size, 100.0).convert("RGB")
    image.save(path, format="JPEG", quality=quality, optimize=False, progressive=progressive)
    return path.stat().st_size


def test_small_jpeg_returns_already_within_target(tmp_path: Path) -> None:
    file_path = tmp_path / "small.jpg"
    original_size = _write_jpeg(file_path, size=(120, 120), quality=80)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) + 10))

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("small.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert result.status is FileStatus.ALREADY_WITHIN_TARGET
    assert result.original_size_bytes == original_size
    assert result.final_size_bytes == original_size
    assert result.failure_reason is None
    assert file_path.stat().st_size == original_size


def test_large_jpeg_is_compressed_and_becomes_smaller(tmp_path: Path) -> None:
    file_path = tmp_path / "large.jpg"
    original_size = _write_jpeg(file_path, size=(2400, 2400), quality=95)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 150), min_image_side=600)

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("large.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert result.status is FileStatus.COMPRESSED_TO_TARGET
    assert result.final_size_bytes is not None
    assert result.final_size_bytes < original_size
    assert file_path.stat().st_size == result.final_size_bytes
    assert result.final_size_bytes <= config.max_size_bytes


def test_corrupted_jpeg_returns_failed_with_corrupted_reason(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.jpg"
    file_path.write_bytes(b"not-a-real-jpeg")
    config = _build_config(tmp_path, max_size_kb=1)

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("broken.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.CORRUPTED_FILE
    assert result.final_size_bytes is None


def test_hard_target_can_return_compressed_but_above_target(tmp_path: Path) -> None:
    file_path = tmp_path / "hard.jpg"
    original_size = _write_jpeg(file_path, size=(2200, 1800), quality=95)
    config = _build_config(tmp_path, max_size_kb=20, min_image_side=1400)

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("hard.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert result.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET
    assert result.failure_reason is FailureReason.IMAGE_CANNOT_REACH_TARGET
    assert result.final_size_bytes is not None
    assert result.final_size_bytes < original_size
    assert result.final_size_bytes > config.max_size_bytes
    assert file_path.stat().st_size == result.final_size_bytes


def test_larger_only_candidates_do_not_overwrite_original_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "worse.jpg"
    original_size = _write_jpeg(file_path, size=(1800, 1800), quality=95)
    original_bytes = file_path.read_bytes()
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 10), min_image_side=1200)

    import zip_compressor.compressors.image_compressor as image_compressor

    larger_candidate = original_bytes + b"still-larger"

    monkeypatch.setattr(
        image_compressor,
        "_find_best_jpeg_candidate",
        lambda source_image, config: (larger_candidate, False),
    )

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("worse.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.IMAGE_CANNOT_REACH_TARGET
    assert result.final_size_bytes is None
    assert file_path.read_bytes() == original_bytes
