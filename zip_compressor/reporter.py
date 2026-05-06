from __future__ import annotations

import logging
import sys
from pathlib import Path

from zip_compressor.models import FileProcessResult, FileStatus, RunSummary


def configure_logging(log_file: Path | None = None) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    existing_handlers = root_logger.handlers

    if not any(
        isinstance(handler, logging.StreamHandler)
        and getattr(handler, "stream", None) is sys.stderr
        for handler in existing_handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        resolved_log_file = log_file.resolve(strict=False)
        if not any(
            isinstance(handler, logging.FileHandler)
            and Path(handler.baseFilename).resolve(strict=False) == resolved_log_file
            for handler in existing_handlers
        ):
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)


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
        failed_files=sum(1 for result in results if result.status is FileStatus.FAILED),
        failures=failures,
    )
