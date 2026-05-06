import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.models import FailureReason, FileCategory, FileProcessResult, FileStatus
from zip_compressor.reporter import build_summary, configure_logging


def test_build_summary_counts_mixed_results() -> None:
    results = [
        FileProcessResult(
            relative_path=Path("small.pdf"),
            category=FileCategory.PDF,
            status=FileStatus.ALREADY_WITHIN_TARGET,
            original_size_bytes=100,
            final_size_bytes=100,
            failure_reason=None,
            message="already small",
        ),
        FileProcessResult(
            relative_path=Path("photo.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.COMPRESSED_TO_TARGET,
            original_size_bytes=4000,
            final_size_bytes=1800,
            failure_reason=None,
            message="compressed",
        ),
        FileProcessResult(
            relative_path=Path("big.png"),
            category=FileCategory.PNG,
            status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
            original_size_bytes=5000,
            final_size_bytes=2600,
            failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
            message="best effort",
        ),
        FileProcessResult(
            relative_path=Path("skip.txt"),
            category=FileCategory.UNSUPPORTED,
            status=FileStatus.SKIPPED_UNSUPPORTED,
            original_size_bytes=50,
            final_size_bytes=None,
            failure_reason=None,
            message="unsupported",
        ),
        FileProcessResult(
            relative_path=Path("broken.pdf"),
            category=FileCategory.PDF,
            status=FileStatus.FAILED,
            original_size_bytes=6000,
            final_size_bytes=None,
            failure_reason=FailureReason.PDF_COMPRESSION_FAILED,
            message="boom",
        ),
    ]

    summary = build_summary(results)

    assert summary.total_files == 5
    assert summary.supported_files == 4
    assert summary.already_within_target == 1
    assert summary.compressed_to_target == 1
    assert summary.compressed_but_above_target == 1
    assert summary.skipped_unsupported == 1
    assert summary.failed_files == 1
    assert [failure.status for failure in summary.failures] == [
        FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
        FileStatus.FAILED,
    ]


def test_summary_failures_include_above_target_and_failed() -> None:
    results = [
        FileProcessResult(
            relative_path=Path("large.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
            original_size_bytes=4000,
            final_size_bytes=2500,
            failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
            message="best effort",
        ),
        FileProcessResult(
            relative_path=Path("broken.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.FAILED,
            original_size_bytes=2000,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message="save failed",
        ),
    ]

    summary = build_summary(results)

    assert [result.status for result in summary.failures] == [
        FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
        FileStatus.FAILED,
    ]


def test_summary_failed_files_only_counts_failed() -> None:
    results = [
        FileProcessResult(
            relative_path=Path("large.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
            original_size_bytes=4000,
            final_size_bytes=2500,
            failure_reason=FailureReason.IMAGE_CANNOT_REACH_TARGET,
            message="best effort",
        ),
        FileProcessResult(
            relative_path=Path("broken.jpg"),
            category=FileCategory.JPEG,
            status=FileStatus.FAILED,
            original_size_bytes=2000,
            final_size_bytes=None,
            failure_reason=FailureReason.IMAGE_SAVE_FAILED,
            message="save failed",
        ),
    ]

    summary = build_summary(results)

    assert summary.failed_files == 1
    assert [result.status for result in summary.failures] == [
        FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
        FileStatus.FAILED,
    ]


def test_configure_logging_writes_utf8_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "compressor.log"

    configure_logging(log_file)
    logger = logging.getLogger("zip_compressor.reporter")
    logger.info("日志写入测试：中文内容")
    logging.shutdown()

    data = log_file.read_bytes()
    assert "中文内容".encode("utf-8") in data


def test_configure_logging_preserves_existing_root_handlers(tmp_path: Path) -> None:
    root = logging.getLogger()
    sentinel = logging.StreamHandler()
    sentinel.set_name("sentinel-handler")
    root.addHandler(sentinel)

    try:
        log_file = tmp_path / "nested" / "compressor.log"

        configure_logging(log_file)
        logging.getLogger("zip_compressor.reporter").info("保留已有 handler")
        logging.shutdown()

        assert sentinel in root.handlers
        assert log_file.exists()
        assert "handler".encode("utf-8") in log_file.read_bytes()
    finally:
        root.removeHandler(sentinel)
