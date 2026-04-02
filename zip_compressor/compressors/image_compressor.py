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