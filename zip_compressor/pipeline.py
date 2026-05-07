from __future__ import annotations

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from zip_compressor.archive import create_zip_from_directory, extract_zip_to_directory
from zip_compressor.compressors.image_compressor import compress_image_file
from zip_compressor.compressors.pdf_compressor import build_pdf_compressor
from zip_compressor.models import (
    CompressionConfig,
    DiscoveredFile,
    FailureReason,
    FileCategory,
    FileProcessResult,
    FileStatus,
    PipelineResult,
)
from zip_compressor.reporter import build_summary
from zip_compressor.scanner import scan_files

logger = logging.getLogger(__name__)


def run_pipeline(config: CompressionConfig) -> PipelineResult:
    results: list[FileProcessResult] = []

    with TemporaryDirectory(prefix="zip-compressor-") as temp_dir:
        working_dir = Path(temp_dir)
        extract_zip_to_directory(config.input_zip, working_dir)
        pdf_compressor = build_pdf_compressor(config)

        for discovered_file in scan_files(working_dir):
            logger.info("processing %s", discovered_file.relative_path.as_posix())
            results.append(_process_discovered_file(discovered_file, config, pdf_compressor))

        create_zip_from_directory(working_dir, config.output_zip)

    return PipelineResult(summary=build_summary(results), results=results)


def _process_discovered_file(
    discovered_file: DiscoveredFile,
    config: CompressionConfig,
    pdf_compressor,
) -> FileProcessResult:
    if discovered_file.category is FileCategory.UNSUPPORTED:
        return FileProcessResult(
            relative_path=discovered_file.relative_path,
            category=discovered_file.category,
            status=FileStatus.SKIPPED_UNSUPPORTED,
            original_size_bytes=discovered_file.size_bytes,
            final_size_bytes=discovered_file.size_bytes,
            failure_reason=FailureReason.UNSUPPORTED_TYPE,
            message="unsupported file type",
        )

    try:
        if discovered_file.category in {FileCategory.JPEG, FileCategory.PNG}:
            return compress_image_file(
                discovered_file.absolute_path,
                discovered_file.relative_path,
                discovered_file.category,
                config,
            )
        if discovered_file.category is FileCategory.PDF:
            return pdf_compressor.compress(
                discovered_file.absolute_path,
                discovered_file.relative_path,
            )
    except Exception as exc:
        return FileProcessResult(
            relative_path=discovered_file.relative_path,
            category=discovered_file.category,
            status=FileStatus.FAILED,
            original_size_bytes=discovered_file.size_bytes,
            final_size_bytes=None,
            failure_reason=FailureReason.UNEXPECTED_ERROR,
            message=str(exc),
        )

    return FileProcessResult(
        relative_path=discovered_file.relative_path,
        category=discovered_file.category,
        status=FileStatus.FAILED,
        original_size_bytes=discovered_file.size_bytes,
        final_size_bytes=None,
        failure_reason=FailureReason.UNEXPECTED_ERROR,
        message=f"no processor for category {discovered_file.category.value}",
    )
