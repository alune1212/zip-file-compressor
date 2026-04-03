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
    failures: list[FileProcessResult] = []
    total_files = len(results)
    supported_files = 0
    already_within_target = 0
    compressed_to_target = 0
    compressed_but_above_target = 0
    skipped_unsupported = 0
    failed_files = 0

    for item in results:
        if item.category is not FileCategory.UNSUPPORTED:
            supported_files += 1
        if item.status is FileStatus.ALREADY_WITHIN_TARGET:
            already_within_target += 1
        elif item.status is FileStatus.COMPRESSED_TO_TARGET:
            compressed_to_target += 1
        elif item.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET:
            compressed_but_above_target += 1
            failures.append(item)
        elif item.status is FileStatus.SKIPPED_UNSUPPORTED:
            skipped_unsupported += 1
        elif item.status is FileStatus.FAILED:
            failed_files += 1
            failures.append(item)

    return RunSummary(
        total_files=total_files,
        supported_files=supported_files,
        already_within_target=already_within_target,
        compressed_to_target=compressed_to_target,
        compressed_but_above_target=compressed_but_above_target,
        skipped_unsupported=skipped_unsupported,
        failed_files=failed_files,
        failures=failures,
    )