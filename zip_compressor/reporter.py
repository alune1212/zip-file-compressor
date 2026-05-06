from __future__ import annotations

import logging
from pathlib import Path

from zip_compressor.models import FileProcessResult, FileStatus, RunSummary


def configure_logging(log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def build_summary(results: list[FileProcessResult]) -> RunSummary:
    supported_results = [
        result for result in results if result.status is not FileStatus.SKIPPED_UNSUPPORTED
    ]
    failures = [
        result
        for result in results
        if result.status in {FileStatus.FAILED, FileStatus.COMPRESSED_BUT_ABOVE_TARGET}
    ]

    return RunSummary(
        total_files=len(results),
        supported_files=len(supported_results),
        already_within_target=sum(
            1 for result in results if result.status is FileStatus.ALREADY_WITHIN_TARGET
        ),
        compressed_to_target=sum(
            1 for result in results if result.status is FileStatus.COMPRESSED_TO_TARGET
        ),
        compressed_but_above_target=sum(
            1 for result in results if result.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET
        ),
        skipped_unsupported=sum(
            1 for result in results if result.status is FileStatus.SKIPPED_UNSUPPORTED
        ),
        failed_files=len(failures),
        failures=failures,
    )
