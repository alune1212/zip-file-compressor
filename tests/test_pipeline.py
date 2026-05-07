import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.models import CompressionConfig, FailureReason, FileStatus
from zip_compressor.pipeline import run_pipeline


def _write_jpeg(path: Path) -> None:
    Image.new("RGB", (80, 80), color="blue").save(path, format="JPEG", quality=80)


def test_run_pipeline_processes_zip_and_writes_output_archive(tmp_path: Path) -> None:
    source_image = tmp_path / "photo.jpg"
    _write_jpeg(source_image)
    input_zip = tmp_path / "input.zip"
    output_zip = tmp_path / "output.zip"

    with zipfile.ZipFile(input_zip, "w") as archive:
        archive.write(source_image, "nested/photo.jpg")
        archive.writestr("nested/readme.txt", "skip me")

    result = run_pipeline(
        CompressionConfig(input_zip=input_zip, output_zip=output_zip, max_size_kb=2000)
    )

    assert output_zip.exists()
    assert result.summary.total_files == 2
    assert len(result.results) == 2
    assert result.summary.skipped_unsupported == 1
    assert any(item.status is FileStatus.SKIPPED_UNSUPPORTED for item in result.results)

    with zipfile.ZipFile(output_zip) as archive:
        names = set(archive.namelist())

    assert "nested/photo.jpg" in names
    assert "nested/readme.txt" in names


def test_run_pipeline_records_unexpected_file_errors_and_continues(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_image = tmp_path / "photo.jpg"
    _write_jpeg(source_image)
    input_zip = tmp_path / "input.zip"
    output_zip = tmp_path / "output.zip"

    with zipfile.ZipFile(input_zip, "w") as archive:
        archive.write(source_image, "broken/photo.jpg")
        archive.writestr("ok/readme.txt", "still packaged")

    def raise_from_image_processing(*args, **kwargs):
        raise RuntimeError("image processing exploded")

    monkeypatch.setattr(
        "zip_compressor.pipeline.compress_image_file",
        raise_from_image_processing,
    )

    result = run_pipeline(
        CompressionConfig(input_zip=input_zip, output_zip=output_zip, max_size_kb=2000)
    )

    failed = [item for item in result.results if item.status is FileStatus.FAILED]
    skipped = [item for item in result.results if item.status is FileStatus.SKIPPED_UNSUPPORTED]

    assert output_zip.exists()
    assert len(result.results) == 2
    assert len(failed) == 1
    assert failed[0].failure_reason is FailureReason.UNEXPECTED_ERROR
    assert "image processing exploded" in failed[0].message
    assert len(skipped) == 1

    with zipfile.ZipFile(output_zip) as archive:
        assert "ok/readme.txt" in set(archive.namelist())
