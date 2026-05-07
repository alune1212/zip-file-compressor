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


def _write_png(
    path: Path,
    *,
    size: tuple[int, int],
    with_alpha: bool = False,
) -> int:
    base = Image.effect_noise(size, 100.0).convert("L")
    channels = [
        base,
        base.point(lambda value: (value * 3) % 256),
        base.point(lambda value: (value * 5) % 256),
    ]
    if with_alpha:
        alpha = Image.linear_gradient("L").resize(size)
        image = Image.merge("RGBA", (*channels, alpha))
    else:
        image = Image.merge("RGB", tuple(channels))
    image.save(path, format="PNG", optimize=False, compress_level=0)
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


def test_min_jpeg_quality_below_default_allows_more_aggressive_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "quality20.jpg"
    original_size = _write_jpeg(file_path, size=(1600, 1600), quality=95)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 50))
    config.min_jpeg_quality = 20

    import zip_compressor.compressors.image_compressor as image_compressor

    qualities_seen: list[int] = []
    target_size = config.max_size_bytes

    def tracking_encode(image: Image.Image, quality: int) -> bytes:
        qualities_seen.append(quality)
        if quality <= 20:
            return b"x" * max(1, target_size - 1)
        return b"x" * (target_size + 100)

    monkeypatch.setattr(image_compressor, "_encode_jpeg", tracking_encode)

    compress_image_file(
        file_path=file_path,
        relative_path=Path("quality20.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert qualities_seen
    assert min(qualities_seen) <= 20


def test_min_jpeg_quality_below_5_is_clamped_without_empty_ladder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "quality1.jpg"
    original_size = _write_jpeg(file_path, size=(1600, 1600), quality=95)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 50))
    config.min_jpeg_quality = 1

    import zip_compressor.compressors.image_compressor as image_compressor

    qualities_seen: list[int] = []
    target_size = config.max_size_bytes

    def tracking_encode(image: Image.Image, quality: int) -> bytes:
        qualities_seen.append(quality)
        if quality <= 5:
            return b"x" * max(1, target_size - 1)
        return b"x" * (target_size + 100)

    monkeypatch.setattr(image_compressor, "_encode_jpeg", tracking_encode)

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("quality1.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert qualities_seen
    assert min(qualities_seen) == 5
    assert result.failure_reason is None


def test_min_jpeg_quality_above_95_does_not_report_empty_ladder_as_save_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "quality96.jpg"
    original_size = _write_jpeg(file_path, size=(1500, 1500), quality=95)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 20))
    config.min_jpeg_quality = 96

    import zip_compressor.compressors.image_compressor as image_compressor
    qualities_seen: list[int] = []

    monkeypatch.setattr(
        image_compressor,
        "_encode_jpeg",
        lambda image, quality: qualities_seen.append(quality) or b"x" * max(1, original_size - 100),
    )

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("quality96.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert qualities_seen
    assert set(qualities_seen) == {95}
    assert result.failure_reason is not FailureReason.IMAGE_SAVE_FAILED


def test_write_failure_returns_structured_image_save_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "write-fail.jpg"
    original_size = _write_jpeg(file_path, size=(1800, 1800), quality=95)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 10))

    import zip_compressor.compressors.image_compressor as image_compressor

    smaller_candidate = b"x" * max(1, original_size - 100)
    monkeypatch.setattr(
        image_compressor,
        "_find_best_jpeg_candidate",
        lambda source_image, config: (smaller_candidate, True),
    )
    monkeypatch.setattr(
        image_compressor,
        "_atomic_write_bytes",
        lambda path, data: (_ for _ in ()).throw(OSError("disk full")),
    )

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("write-fail.jpg"),
        category=FileCategory.JPEG,
        config=config,
    )

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.IMAGE_SAVE_FAILED
    assert result.final_size_bytes is None


def test_large_png_is_processed_and_stays_png_by_default(tmp_path: Path) -> None:
    file_path = tmp_path / "image.png"
    original_size = _write_png(file_path, size=(1800, 1800))
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 100), min_image_side=700)

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("image.png"),
        category=FileCategory.PNG,
        config=config,
    )

    assert result.status in {
        FileStatus.COMPRESSED_TO_TARGET,
        FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
    }
    assert result.relative_path.suffix == ".png"
    assert file_path.exists()
    assert result.final_size_bytes is not None
    assert result.final_size_bytes < original_size
    assert file_path.stat().st_size == result.final_size_bytes


def test_png_without_alpha_can_convert_to_jpg_when_enabled(tmp_path: Path) -> None:
    file_path = tmp_path / "convertible.png"
    original_size = _write_png(file_path, size=(1800, 1800), with_alpha=False)
    config = _build_config(tmp_path, max_size_kb=320, min_image_side=700)
    config.png_allow_jpg = True

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("convertible.png"),
        category=FileCategory.PNG,
        config=config,
    )

    converted_path = tmp_path / "convertible.jpg"
    assert result.status is FileStatus.COMPRESSED_TO_TARGET
    assert result.relative_path == Path("convertible.jpg")
    assert result.relative_path.suffix == ".jpg"
    assert result.category is FileCategory.JPEG
    assert converted_path.exists()
    assert not file_path.exists()
    assert result.final_size_bytes is not None
    assert result.final_size_bytes < original_size
    assert converted_path.stat().st_size == result.final_size_bytes


def test_png_with_alpha_does_not_convert_to_jpg_even_when_enabled(tmp_path: Path) -> None:
    file_path = tmp_path / "alpha.png"
    original_size = _write_png(file_path, size=(1800, 1800), with_alpha=True)
    config = _build_config(tmp_path, max_size_kb=max(1, (original_size // 1024) - 100), min_image_side=700)
    config.png_allow_jpg = True

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("alpha.png"),
        category=FileCategory.PNG,
        config=config,
    )

    assert result.status in {
        FileStatus.COMPRESSED_TO_TARGET,
        FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
    }
    assert result.relative_path == Path("alpha.png")
    assert file_path.exists()
    assert not (tmp_path / "alpha.jpg").exists()
    assert result.final_size_bytes is not None
    assert result.final_size_bytes < original_size


def test_corrupted_png_returns_failed_with_corrupted_reason(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.png"
    file_path.write_bytes(b"not-a-real-png")
    config = _build_config(tmp_path, max_size_kb=1)

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("broken.png"),
        category=FileCategory.PNG,
        config=config,
    )

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.CORRUPTED_FILE
    assert result.final_size_bytes is None


def test_png_to_jpg_delete_failure_rolls_back_new_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "rollback.png"
    original_size = _write_png(file_path, size=(1800, 1800), with_alpha=False)
    original_bytes = file_path.read_bytes()
    config = _build_config(tmp_path, max_size_kb=320, min_image_side=700)
    config.png_allow_jpg = True

    import zip_compressor.compressors.image_compressor as image_compressor

    def failing_delete(original_path: Path, replacement_path: Path) -> None:
        raise OSError("cannot remove original png")

    monkeypatch.setattr(
        image_compressor,
        "_delete_original_after_replacement",
        failing_delete,
    )

    result = compress_image_file(
        file_path=file_path,
        relative_path=Path("rollback.png"),
        category=FileCategory.PNG,
        config=config,
    )

    converted_path = tmp_path / "rollback.jpg"
    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.IMAGE_SAVE_FAILED
    assert result.final_size_bytes is None
    assert result.relative_path == Path("rollback.jpg")
    assert file_path.exists()
    assert file_path.read_bytes() == original_bytes
    assert not converted_path.exists()


def test_unsupported_category_still_raises_value_error(tmp_path: Path) -> None:
    file_path = tmp_path / "image.bin"
    file_path.write_bytes(b"not-an-image")
    config = _build_config(tmp_path, max_size_kb=1)

    with pytest.raises(ValueError, match="supports JPEG and PNG"):
        compress_image_file(
            file_path=file_path,
            relative_path=Path("image.bin"),
            category=FileCategory.UNSUPPORTED,
            config=config,
        )
