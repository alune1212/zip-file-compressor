from pathlib import Path

from zip_compressor.models import (
    CompressionConfig,
    FailureReason,
    FileCategory,
    FileProcessResult,
    FileStatus,
)


def test_default_config_uses_expected_limits(tmp_path: Path) -> None:
    config = CompressionConfig(input_zip=tmp_path / "in.zip", output_zip=tmp_path / "out.zip")
    assert config.max_size_kb == 2000
    assert config.png_allow_jpg is False
    assert config.pdf_strategy == "none"
    assert config.min_jpeg_quality == 35


def test_file_process_result_reports_target_match() -> None:
    result = FileProcessResult(
        relative_path=Path("nested/photo.jpg"),
        category=FileCategory.JPEG,
        status=FileStatus.COMPRESSED_TO_TARGET,
        original_size_bytes=4_000_000,
        final_size_bytes=1_500_000,
        failure_reason=None,
        message="compressed",
    )
    assert result.reached_target is True
    assert result.was_skipped is False


def test_file_process_result_flags_failures() -> None:
    result = FileProcessResult(
        relative_path=Path("broken.pdf"),
        category=FileCategory.PDF,
        status=FileStatus.FAILED,
        original_size_bytes=3_500_000,
        final_size_bytes=None,
        failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
        message="ghostscript missing",
    )
    assert result.reached_target is False
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE