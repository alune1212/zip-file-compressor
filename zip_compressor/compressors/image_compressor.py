from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ..models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus

JPEG_QUALITIES = [95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35]
SCALE_STEPS = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6]
PNG_LEVELS = [9, 8, 7, 6]
PNG_COLORS = [256, 128, 64]


def _save_jpeg_candidate(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


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

    if config.force_jpg:
        jpeg_bytes = _save_jpeg_candidate(base_image.convert("RGB"), quality=70)
        new_path = file_path.with_suffix(".jpg")
        if file_path.exists():
            file_path.unlink()
        new_path.write_bytes(jpeg_bytes)
        return FileProcessResult(relative_path.with_suffix(".jpg"), FileCategory.PNG, FileStatus.COMPRESSED_TO_TARGET if len(jpeg_bytes) <= config.max_size_bytes else FileStatus.COMPRESSED_BUT_ABOVE_TARGET, original_size, len(jpeg_bytes), None if len(jpeg_bytes) <= config.max_size_bytes else FailureReason.IMAGE_CANNOT_REACH_TARGET, "force jpg conversion")

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


def compress_image_file(
    file_path: Path,
    relative_path: Path,
    category: FileCategory,
    config: CompressionConfig,
) -> FileProcessResult:
    original_size = file_path.stat().st_size
    if original_size <= config.max_size_bytes:
        return FileProcessResult(relative_path, category, FileStatus.ALREADY_WITHIN_TARGET, original_size, original_size, None, "already within target")

    if category is FileCategory.PNG:
        return _compress_png(file_path, relative_path, original_size, config)

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