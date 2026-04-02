import logging
from pathlib import Path

from .models import FileCategory, FileProcessResult, FileStatus, RunSummary


def configure_logging(log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", handlers=handlers, force=True)


def build_summary(results: list[FileProcessResult]) -> RunSummary:
    failures = [item for item in results if item.status is FileStatus.FAILED or item.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET]
    return RunSummary(
        total_files=len(results),
        supported_files=sum(1 for item in results if item.category is not FileCategory.UNSUPPORTED),
        already_within_target=sum(1 for item in results if item.status is FileStatus.ALREADY_WITHIN_TARGET),
        compressed_to_target=sum(1 for item in results if item.status is FileStatus.COMPRESSED_TO_TARGET),
        compressed_but_above_target=sum(1 for item in results if item.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET),
        skipped_unsupported=sum(1 for item in results if item.status is FileStatus.SKIPPED_UNSUPPORTED),
        failed_files=sum(1 for item in results if item.status is FileStatus.FAILED),
        failures=failures,
    )