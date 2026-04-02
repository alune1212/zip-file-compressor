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