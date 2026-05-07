"""Command line entry point for the ZIP compressor package."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from zip_compressor.models import (
    DEFAULT_MAX_SIZE_KB,
    DEFAULT_MIN_IMAGE_SIDE,
    DEFAULT_MIN_JPEG_QUALITY,
    CompressionConfig,
    FileProcessResult,
    PipelineResult,
)
from zip_compressor.pipeline import run_pipeline
from zip_compressor.reporter import configure_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compress supported files inside a ZIP archive and rebuild a new ZIP while "
            "preserving the original directory structure."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="source ZIP file path")
    parser.add_argument("--output", required=True, type=Path, help="output ZIP file path")
    parser.add_argument(
        "--max-size-kb",
        type=int,
        default=DEFAULT_MAX_SIZE_KB,
        help=f"target size per supported file in KB, default: {DEFAULT_MAX_SIZE_KB}",
    )
    parser.add_argument(
        "--png-allow-jpg",
        action="store_true",
        help="allow non-transparent PNG files to be converted to JPG when needed",
    )
    parser.add_argument(
        "--force-jpg",
        action="store_true",
        help="force PNG files to be converted to JPG when they need processing",
    )
    parser.add_argument(
        "--pdf-strategy",
        choices=("none", "ghostscript"),
        default="none",
        help="PDF compression strategy, default: none",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="optional UTF-8 log file path",
    )
    parser.add_argument(
        "--min-image-side",
        type=int,
        default=DEFAULT_MIN_IMAGE_SIDE,
        help=f"minimum image side after scaling, default: {DEFAULT_MIN_IMAGE_SIDE}",
    )
    parser.add_argument(
        "--min-jpeg-quality",
        type=int,
        default=DEFAULT_MIN_JPEG_QUALITY,
        help=(
            "minimum JPEG quality used by iterative image compression, "
            f"default: {DEFAULT_MIN_JPEG_QUALITY}"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.max_size_kb <= 0:
        parser.error("--max-size-kb must be greater than 0")
    if args.min_image_side <= 0:
        parser.error("--min-image-side must be greater than 0")
    if args.min_jpeg_quality <= 0:
        parser.error("--min-jpeg-quality must be greater than 0")
    if not args.input.is_file():
        parser.error(f"--input must point to an existing ZIP file: {args.input}")

    config = CompressionConfig(
        input_zip=args.input,
        output_zip=args.output,
        max_size_kb=args.max_size_kb,
        png_allow_jpg=args.png_allow_jpg,
        force_jpg=args.force_jpg,
        pdf_strategy=args.pdf_strategy,
        log_file=args.log_file,
        min_image_side=args.min_image_side,
        min_jpeg_quality=args.min_jpeg_quality,
    )
    configure_logging(config.log_file)

    try:
        result = run_pipeline(config)
    except Exception as exc:
        logger.exception("zip compression failed")
        print(f"处理失败: {exc}", file=sys.stderr)
        return 1

    _print_result(result)
    return 0


def _print_result(result: PipelineResult) -> None:
    summary = result.summary
    print("处理完成")
    print(f"总文件数: {summary.total_files}")
    print(f"支持类型文件数: {summary.supported_files}")
    print(f"成功压缩到目标大小: {summary.compressed_to_target}")
    print(f"原本已小于等于阈值: {summary.already_within_target}")
    print(f"压缩后仍超限: {summary.compressed_but_above_target}")
    print(f"跳过不支持类型: {summary.skipped_unsupported}")
    print(f"压缩失败: {summary.failed_files}")

    if summary.failures:
        print("失败清单:")
        for failure in summary.failures:
            print(f"- {_format_failure(failure)}")


def _format_failure(result: FileProcessResult) -> str:
    reason = result.failure_reason.value if result.failure_reason is not None else "unknown"
    return f"{result.relative_path.as_posix()} [{reason}] {result.message}"


if __name__ == "__main__":
    raise SystemExit(main())
