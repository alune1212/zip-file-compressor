from pathlib import Path

from zip_compressor.compressors.pdf_compressor import build_pdf_compressor
from zip_compressor.models import CompressionConfig, FailureReason, FileCategory, FileStatus


def test_build_pdf_compressor_defaults_to_noop(tmp_path: Path) -> None:
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip")
    compressor = build_pdf_compressor(config)
    assert compressor.__class__.__name__ == "NoopPdfCompressor"


def test_noop_pdf_compressor_marks_file_as_unavailable(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip")

    compressor = build_pdf_compressor(config)
    result = compressor.compress(pdf_path, Path("sample.pdf"))

    assert result.category is FileCategory.PDF
    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE