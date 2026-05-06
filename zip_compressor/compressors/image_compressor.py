from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from zip_compressor.models import (
    CompressionConfig,
    FailureReason,
    FileCategory,
    FileProcessResult,
    FileStatus,
)

_JPEG_QUALITY_STEPS = (95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35)
_SCALE_STEPS = (1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6)
_MIN_ALLOWED_JPEG_QUALITY = 5
_MAX_ALLOWED_JPEG_QUALITY = 95


def compress_image_file(
    file_path: Path,
    relative_path: Path,
    category: FileCategory,
    config: CompressionConfig,
) -> FileProcessResult:
    if category not in {FileCategory.JPEG, FileCategory.PNG}:
        raise ValueError(
            f"compress_image_file only supports JPEG and PNG inputs, got {category.value}"
        )

    original_size = file_path.stat().st_size

    try:
        source_image = _load_image(file_path)
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.CORRUPTED_FILE,
            message=f"failed to open {category.value}: {exc}",
        )

    if original_size <= config.max_size_bytes:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.ALREADY_WITHIN_TARGET,
            original_size_bytes=original_size,
            final_size_bytes=original_size,
            failure_reason=None,
            message=f"{category.value} already within target size",
        )

    if category is FileCategory.PNG:
        return _compress_png_file(
            file_path=file_path,
            relative_path=relative_path,
            source_image=source_image,
            original_size=original_size,
            config=config,
        )

    try:
        best_bytes, reached_target = _find_best_jpeg_candidate(source_image, config)
    except OSError as exc:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message=f"failed to encode jpeg: {exc}",
        )

    if best_bytes is None:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message="no jpeg candidate could be encoded",
        )

    if len(best_bytes) >= original_size:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
            message="jpeg candidates did not reduce file size",
        )

    try:
        _atomic_write_bytes(file_path, best_bytes)
    except OSError as exc:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message=f"failed to write jpeg: {exc}",
        )

    final_size = len(best_bytes)
    if reached_target:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.COMPRESSED_TO_TARGET,
            original_size_bytes=original_size,
            final_size_bytes=final_size,
            failure_reason=None,
            message="jpeg compressed to target size",
        )

    return FileProcessResult(
        relative_path=relative_path,
        category=category,
        status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
        original_size_bytes=original_size,
        final_size_bytes=final_size,
        failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
        message="jpeg compressed, but target size could not be reached",
    )


def _load_image(file_path: Path) -> Image.Image:
    with Image.open(file_path) as image:
        image.load()
        return image.copy()


def _compress_png_file(
    file_path: Path,
    relative_path: Path,
    source_image: Image.Image,
    original_size: int,
    config: CompressionConfig,
) -> FileProcessResult:
    try:
        best_png_bytes, png_reached_target = _find_best_png_candidate(source_image, config)
    except OSError as exc:
        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PNG,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message=f"failed to encode png: {exc}",
        )

    best_bytes = best_png_bytes
    output_path = file_path
    output_relative_path = relative_path
    output_category = FileCategory.PNG
    output_message = "png compressed, but target size could not be reached"
    reached_target = png_reached_target

    if not reached_target and config.png_allow_jpg and not _image_uses_transparency(source_image):
        try:
            best_jpeg_bytes, jpeg_reached_target = _find_best_jpeg_candidate(source_image, config)
        except OSError as exc:
            return FileProcessResult(
                relative_path=relative_path,
                category=FileCategory.PNG,
                status=FileStatus.FAILED,
                original_size_bytes=original_size,
                final_size_bytes=None,
                failure_reason=FailureReason.IMAGE_SAVE_FAILED,
                message=f"failed to encode png as jpeg: {exc}",
            )

        if best_jpeg_bytes is not None and (
            best_bytes is None or len(best_jpeg_bytes) < len(best_bytes)
        ):
            best_bytes = best_jpeg_bytes
            output_path = file_path.with_suffix(".jpg")
            output_relative_path = relative_path.with_suffix(".jpg")
            output_category = FileCategory.JPEG
            output_message = "png converted to jpeg, but target size could not be reached"
            reached_target = jpeg_reached_target
            if jpeg_reached_target:
                output_message = "png converted to jpeg and compressed to target size"

    if best_bytes is None:
        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PNG,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message="no png candidate could be encoded",
        )

    if len(best_bytes) >= original_size:
        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PNG,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
            message="png candidates did not reduce file size",
        )

    try:
        final_path = _write_image_result(file_path, output_path, best_bytes)
    except OSError as exc:
        return FileProcessResult(
            relative_path=output_relative_path,
            category=output_category,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message=f"failed to write png output: {exc}",
        )

    final_size = len(best_bytes)
    if reached_target:
        return FileProcessResult(
            relative_path=output_relative_path,
            category=output_category,
            status=FileStatus.COMPRESSED_TO_TARGET,
            original_size_bytes=original_size,
            final_size_bytes=final_size,
            failure_reason=None,
            message=(
                "png compressed to target size"
                if final_path.suffix.lower() == ".png"
                else "png converted to jpeg and compressed to target size"
            ),
        )

    return FileProcessResult(
        relative_path=output_relative_path,
        category=output_category,
        status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
        original_size_bytes=original_size,
        final_size_bytes=final_size,
        failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
        message=output_message,
    )


def _find_best_jpeg_candidate(
    source_image: Image.Image,
    config: CompressionConfig,
) -> tuple[bytes | None, bool]:
    rgb_source = source_image.convert("RGB")
    best_bytes: bytes | None = None
    min_quality = config.min_jpeg_quality

    for scale in _eligible_scales(rgb_source.size, config.min_image_side):
        candidate_image = _resize_image(rgb_source, scale)
        for quality in _eligible_qualities(min_quality):
            candidate_bytes = _encode_jpeg(candidate_image, quality)
            if best_bytes is None or len(candidate_bytes) < len(best_bytes):
                best_bytes = candidate_bytes
            if len(candidate_bytes) <= config.max_size_bytes:
                return candidate_bytes, True

    return best_bytes, False


def _find_best_png_candidate(
    source_image: Image.Image,
    config: CompressionConfig,
) -> tuple[bytes | None, bool]:
    best_bytes: bytes | None = None

    for scale in _eligible_scales(source_image.size, config.min_image_side):
        candidate_image = _resize_image(source_image, scale)
        for variant in _png_candidate_variants(candidate_image):
            candidate_bytes = _encode_png(variant)
            if best_bytes is None or len(candidate_bytes) < len(best_bytes):
                best_bytes = candidate_bytes
            if len(candidate_bytes) <= config.max_size_bytes:
                return candidate_bytes, True

    return best_bytes, False


def _eligible_scales(image_size: tuple[int, int], min_image_side: int) -> list[float]:
    width, height = image_size
    shortest_side = min(width, height)
    scales: list[float] = []

    for scale in _SCALE_STEPS:
        if scale == 1.0:
            scales.append(scale)
            continue
        scaled_shortest_side = int(shortest_side * scale)
        if scaled_shortest_side >= min_image_side:
            scales.append(scale)

    return scales or [1.0]


def _eligible_qualities(min_quality: int) -> list[int]:
    clamped_min_quality = min(max(min_quality, _MIN_ALLOWED_JPEG_QUALITY), _MAX_ALLOWED_JPEG_QUALITY)
    qualities = [quality for quality in _JPEG_QUALITY_STEPS if quality >= clamped_min_quality]
    if qualities:
        last_quality = qualities[-1]
        if last_quality != clamped_min_quality:
            qualities.append(clamped_min_quality)
        return qualities
    return [clamped_min_quality]


def _resize_image(source_image: Image.Image, scale: float) -> Image.Image:
    if scale == 1.0:
        return source_image

    width, height = source_image.size
    resized_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return source_image.resize(resized_size, Image.Resampling.LANCZOS)


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return buffer.getvalue()


def _encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    save_kwargs = {
        "format": "PNG",
        "optimize": True,
        "compress_level": 9,
    }
    transparency = image.info.get("transparency")
    if transparency is not None:
        save_kwargs["transparency"] = transparency
    image.save(buffer, **save_kwargs)
    return buffer.getvalue()


def _png_candidate_variants(image: Image.Image) -> list[Image.Image]:
    variants = [image]
    quantize_colors = (256, 128)

    for colors in quantize_colors:
        if image.mode in {"RGBA", "LA"}:
            variants.append(
                image.quantize(
                    colors=colors,
                    method=Image.Quantize.FASTOCTREE,
                    dither=Image.Dither.NONE,
                )
            )
            continue

        if image.mode in {"RGB", "L", "P"}:
            variants.append(
                image.quantize(
                    colors=colors,
                    method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.NONE,
                )
            )

    return variants


def _image_uses_transparency(image: Image.Image) -> bool:
    if "transparency" in image.info:
        return True
    if "A" not in image.getbands():
        return False
    alpha = image.getchannel("A")
    min_alpha, max_alpha = alpha.getextrema()
    return min_alpha < 255 or max_alpha < 255


def _write_image_result(original_path: Path, output_path: Path, data: bytes) -> Path:
    _atomic_write_bytes(output_path, data)
    if output_path == original_path:
        return output_path

    try:
        _delete_original_after_replacement(original_path, output_path)
    except OSError:
        _cleanup_replacement_after_failed_delete(output_path)
        raise

    return output_path


def _delete_original_after_replacement(original_path: Path, replacement_path: Path) -> None:
    original_path.unlink()


def _cleanup_replacement_after_failed_delete(replacement_path: Path) -> None:
    try:
        replacement_path.unlink(missing_ok=True)
    except OSError:
        pass


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=path.parent) as temp_file:
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        temp_path.replace(path)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
