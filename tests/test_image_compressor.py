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