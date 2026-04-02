import argparse
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from .archive import create_zip_from_directory, extract_zip_to_directory
from .compressors.image_compressor import compress_image_file
from .compressors.pdf_compressor import build_pdf_compressor
from .models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus, PipelineResult
from .reporter import build_summary, configure_logging
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


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compress supported files inside a ZIP archive.")
    parser.add_argument("--input", required=True, dest="input_zip", type=Path)
    parser.add_argument("--output", required=True, dest="output_zip", type=Path)
    parser.add_argument("--max-size-kb", type=int, default=2000)
    parser.add_argument("--png-allow-jpg", action="store_true")
    parser.add_argument("--pdf-strategy", choices=["none", "ghostscript"], default="none")
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--min-image-side", type=int, default=800)
    parser.add_argument("--min-jpeg-quality", type=int, default=35)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    config = CompressionConfig(
        input_zip=args.input_zip,
        output_zip=args.output_zip,
        max_size_kb=args.max_size_kb,
        png_allow_jpg=args.png_allow_jpg,
        pdf_strategy=args.pdf_strategy,
        log_file=args.log_file,
        min_image_side=args.min_image_side,
        min_jpeg_quality=args.min_jpeg_quality,
    )
    configure_logging(config.log_file)
    pipeline_result = run_pipeline(config)
    logging.info("Total files: %s", pipeline_result.summary.total_files)
    logging.info("Compressed to target: %s", pipeline_result.summary.compressed_to_target)
    logging.info("Already within target: %s", pipeline_result.summary.already_within_target)
    logging.info("Failed files: %s", pipeline_result.summary.failed_files)
    for failure in pipeline_result.summary.failures:
        logging.info("Failure: %s -> %s", failure.relative_path.as_posix(), failure.message)
    return 0 if pipeline_result.summary.failed_files == 0 else 1