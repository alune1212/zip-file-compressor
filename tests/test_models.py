import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def test_file_process_result_flags_non_skipped_states() -> None:
    result = FileProcessResult(
        relative_path=Path("broken.pdf"),
        category=FileCategory.PDF,
        status=FileStatus.FAILED,
        original_size_bytes=3_500_000,
        final_size_bytes=None,
        failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
        message="ghostscript missing",
    )
    assert result.was_skipped is False
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE


def test_module_entrypoint_help_runs_without_import_error() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zip_compressor", "--help"],
        check=False,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )
    assert completed.returncode == 0
    assert "--input" in completed.stdout


def test_file_process_result_rejects_failed_status_with_final_size() -> None:
    with pytest.raises(ValueError, match="failed"):
        FileProcessResult(
            relative_path=Path("broken.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.FAILED,
            original_size_bytes=2_000_000,
            final_size_bytes=1_800_000,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message="save error",
        )


def test_file_process_result_allows_above_target_with_failure_reason() -> None:
    result = FileProcessResult(
        relative_path=Path("large.jpg"),
        category=FileCategory.JPEG,
        status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
        original_size_bytes=4_000_000,
        final_size_bytes=2_200_000,
        failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
        message="best effort",
    )
    assert result.failure_reason is FailureReason.IMAGE_CANNOT_REACH_TARGET
    assert result.reached_target is False


def test_file_process_result_rejects_failed_status_without_failure_reason() -> None:
    with pytest.raises(ValueError, match="failure_reason"):
        FileProcessResult(
            relative_path=Path("broken.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.FAILED,
            original_size_bytes=2_000_000,
            final_size_bytes=None,
            failure_reason=None,
            message="save error",
        )
