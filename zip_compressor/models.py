from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class FileCategory(str, Enum):
    PDF = "pdf"
    JPEG = "jpeg"
    PNG = "png"
    UNSUPPORTED = "unsupported"


class FileStatus(str, Enum):
    ALREADY_WITHIN_TARGET = "already_within_target"
    COMPRESSED_TO_TARGET = "compressed_to_target"
    COMPRESSED_BUT_ABOVE_TARGET = "compressed_but_above_target"
    SKIPPED_UNSUPPORTED = "skipped_unsupported"
    FAILED = "failed"


class FailureReason(str, Enum):
    UNSUPPORTED_TYPE = "unsupported_type"
    CORRUPTED_FILE = "corrupted_file"
    IMAGE_OPEN_FAILED = "image_open_failed"
    IMAGE_SAVE_FAILED = "image_save_failed"
    IMAGE_CANNOT_REACH_TARGET = "image_cannot_reach_target"
    PDF_STRATEGY_UNAVAILABLE = "pdf_strategy_unavailable"
    PDF_COMPRESSION_FAILED = "pdf_compression_failed"
    ZIP_EXTRACT_ERROR = "zip_extract_error"
    ZIP_PACK_ERROR = "zip_pack_error"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(slots=True)
class CompressionConfig:
    input_zip: Path
    output_zip: Path
    max_size_kb: int = 2000
    png_allow_jpg: bool = False
    pdf_strategy: str = "none"
    log_file: Path | None = None
    min_image_side: int = 800
    min_jpeg_quality: int = 35

    @property
    def max_size_bytes(self) -> int:
        return self.max_size_kb * 1024


@dataclass(slots=True)
class DiscoveredFile:
    absolute_path: Path
    relative_path: Path
    category: FileCategory
    size_bytes: int


@dataclass(slots=True)
class FileProcessResult:
    relative_path: Path
    category: FileCategory
    status: FileStatus
    original_size_bytes: int
    final_size_bytes: int | None
    failure_reason: FailureReason | None
    message: str

    @property
    def reached_target(self) -> bool:
        return self.status in {
            FileStatus.ALREADY_WITHIN_TARGET,
            FileStatus.COMPRESSED_TO_TARGET,
        }

    @property
    def was_skipped(self) -> bool:
        return self.status is FileStatus.SKIPPED_UNSUPPORTED


@dataclass(slots=True)
class RunSummary:
    total_files: int
    supported_files: int
    already_within_target: int
    compressed_to_target: int
    compressed_but_above_target: int
    skipped_unsupported: int
    failed_files: int
    failures: list[FileProcessResult]