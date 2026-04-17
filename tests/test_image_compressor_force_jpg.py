from pathlib import Path
from PIL import Image
from zip_compressor.compressors.image_compressor import compress_image_file
from zip_compressor.models import CompressionConfig, FileCategory

def test_png_force_jpg_conversion(tmp_path):
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        force_jpg=True,
        max_size_kb=1,  # Very small limit to force compression
    )
    # Create a larger PNG file that exceeds 1KB
    png_path = tmp_path / "test.png"
    img = Image.new('RGB', (500, 500), color='red')
    img.save(png_path, 'PNG')

    result = compress_image_file(png_path, Path("test.png"), FileCategory.PNG, config)

    assert result.relative_path.suffix == ".jpg"
    assert not png_path.exists()
    assert (tmp_path / "test.jpg").exists()