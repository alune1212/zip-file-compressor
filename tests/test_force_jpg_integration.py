import zipfile
from pathlib import Path

from PIL import Image

from zip_compressor.models import CompressionConfig
from zip_compressor.pipeline import run_pipeline


def test_force_jpg_end_to_end(tmp_path: Path) -> None:
    """Integration test verifying force_jpg converts PNG to JPG and keeps existing JPEGs."""
    input_zip = tmp_path / "input.zip"
    output_zip = tmp_path / "output.zip"

    with zipfile.ZipFile(input_zip, "w") as zf:
        # Create and add a PNG file (larger to exceed max_size_kb=1)
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (500, 500), color="red")
        img.save(png_path, "PNG")
        zf.write(png_path, "test.png")

        # Create and add a JPEG file (larger to exceed max_size_kb=1)
        jpg_path = tmp_path / "test.jpg"
        img.save(jpg_path, "JPEG", quality=95)
        zf.write(jpg_path, "test.jpg")

    config = CompressionConfig(
        input_zip=input_zip,
        output_zip=output_zip,
        force_jpg=True,
        max_size_kb=1,  # Very small limit to ensure PNG gets processed
    )

    result = run_pipeline(config)

    # Verify output ZIP exists
    assert output_zip.exists()

    # Verify output ZIP contains only .jpg files (no PNG)
    with zipfile.ZipFile(output_zip, "r") as zf:
        names = zf.namelist()
        for name in names:
            if name.endswith((".png", ".pdf")):
                assert False, f"Found non-JPG file: {name}"
        # Should have test.png converted to .jpg and test.jpg
        assert any("test.jpg" in n for n in names)