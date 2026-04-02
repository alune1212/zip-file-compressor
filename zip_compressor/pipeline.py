import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from .archive import create_zip_from_directory, extract_zip_to_directory
from .compressors.image_compressor import compress_image_file
from .compressors.pdf_compressor import build_pdf_compressor
from .models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus, PipelineResult
from .reporter import build_summary
from .scanner import scan_files


def run_pipeline(config: CompressionConfig) -> PipelineResult:
    results: list[FileProcessResult] = []
    pdf_compressor = build_pdf_compressor(config)

    with TemporaryDirectory(prefix="zip-compressor-") as temp_dir:
        working_dir = Path(temp_dir)
        extract_zip_to_directory(config.input_zip, working_dir)

        for discovered in scan_files(working_dir):
            logging.info("Processing %s", discovered.relative_path.as_posix())
            if discovered.category is FileCategory.UNSUPPORTED:
                results.append(
                    FileProcessResult(
                        relative_path=discovered.relative_path,
                        category=discovered.category,
                        status=FileStatus.SKIPPED_UNSUPPORTED,
                        original_size_bytes=discovered.size_bytes,
                        final_size_bytes=discovered.size_bytes,
                        failure_reason=FailureReason.UNSUPPORTED_TYPE,
                        message="unsupported file type",
                    )
                )
                continue

            try:
                if discovered.category in {FileCategory.JPEG, FileCategory.PNG}:
                    result = compress_image_file(discovered.absolute_path, discovered.relative_path, discovered.category, config)
                else:
                    result = pdf_compressor.compress(discovered.absolute_path, discovered.relative_path)
                results.append(result)
            except Exception as exc:
                results.append(
                    FileProcessResult(
                        relative_path=discovered.relative_path,
                        category=discovered.category,
                        status=FileStatus.FAILED,
                        original_size_bytes=discovered.size_bytes,
                        final_size_bytes=None,
                        failure_reason=FailureReason.UNEXPECTED_ERROR,
                        message=str(exc),
                    )
                )

        create_zip_from_directory(working_dir, config.output_zip)

    summary = build_summary(results)
    return PipelineResult(summary=summary, results=results)