from pathlib import Path

from zip_compressor.models import FailureReason, FileCategory, FileProcessResult, FileStatus
from zip_compressor.reporter import build_summary


def test_build_summary_counts_each_outcome() -> None:
    results = [
        FileProcessResult(Path("a.jpg"), FileCategory.JPEG, FileStatus.ALREADY_WITHIN_TARGET, 10, 10, None, "ok"),
        FileProcessResult(Path("b.png"), FileCategory.PNG, FileStatus.COMPRESSED_TO_TARGET, 100, 50, None, "ok"),
        FileProcessResult(
            Path("c.pdf"),
            FileCategory.PDF,
            FileStatus.FAILED,
            100,
            None,
            FailureReason.PDF_STRATEGY_UNAVAILABLE,
            "missing",
        ),
        FileProcessResult(
            Path("d.txt"),
            FileCategory.UNSUPPORTED,
            FileStatus.SKIPPED_UNSUPPORTED,
            20,
            20,
            FailureReason.UNSUPPORTED_TYPE,
            "skip",
        ),
    ]

    summary = build_summary(results)

    assert summary.total_files == 4
    assert summary.supported_files == 3
    assert summary.already_within_target == 1
    assert summary.compressed_to_target == 1
    assert summary.failed_files == 1
    assert summary.skipped_unsupported == 1
    assert summary.failures[0].relative_path == Path("c.pdf")