from __future__ import annotations

import io
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


def compress_image_file(
    file_path: Path,
    relative_path: Path,
    category: FileCategory,
    config: CompressionConfig,
) -> FileProcessResult:
    original_size = file_path.stat().st_size
    if category is not FileCategory.JPEG:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.SKIPPED_UNSUPPORTED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=None,
            message=f"unsupported image category: {category.value}",
        )

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
            message=f"failed to open jpeg: {exc}",
        )

    if original_size <= config.max_size_bytes:
        return FileProcessResult(
            relative_path=relative_path,
            category=category,
            status=FileStatus.ALREADY_WITHIN_TARGET,
            original_size_bytes=original_size,
            final_size_bytes=original_size,
            failure_reason=None,
            message="jpeg already within target size",
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

    file_path.write_bytes(best_bytes)
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
        return image.convert("RGB")


def _find_best_jpeg_candidate(
    source_image: Image.Image,
    config: CompressionConfig,
) -> tuple[bytes | None, bool]:
    best_bytes: bytes | None = None
    min_quality = config.min_jpeg_quality

    for scale in _eligible_scales(source_image.size, config.min_image_side):
        candidate_image = _resize_image(source_image, scale)
        for quality in _eligible_qualities(min_quality):
            candidate_bytes = _encode_jpeg(candidate_image, quality)
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
    return [quality for quality in _JPEG_QUALITY_STEPS if quality >= min_quality]


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
