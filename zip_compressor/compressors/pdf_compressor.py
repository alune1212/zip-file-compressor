from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from ..models import CompressionConfig, FailureReason, FileCategory, FileProcessResult, FileStatus

GS_PDF_SETTINGS = ["/printer", "/ebook", "/screen"]


@dataclass(slots=True)
class NoopPdfCompressor:
    config: CompressionConfig

    def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
        original_size = file_path.stat().st_size
        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PDF,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
            message="No PDF compression strategy is enabled.",
        )


@dataclass(slots=True)
class GhostscriptPdfCompressor:
    config: CompressionConfig
    executable: str

    def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
        original_size = file_path.stat().st_size
        if original_size <= self.config.max_size_bytes:
            return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.ALREADY_WITHIN_TARGET, original_size, original_size, None, "already within target")
        settings = GS_PDF_SETTINGS
        best_size = original_size
        best_output: bytes | None = None
        for setting in settings:
            candidate_path = file_path.with_suffix(".candidate.pdf")
            command = [
                self.executable,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={setting}",
                "-dNOPAUSE",
                "-dBATCH",
                "-dQUIET",
                f"-sOutputFile={candidate_path}",
                str(file_path),
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                continue  # Try next setting instead of failing entirely
            candidate_size = candidate_path.stat().st_size
            candidate_bytes = candidate_path.read_bytes()
            candidate_path.unlink(missing_ok=True)
            if candidate_size < best_size:
                best_size = candidate_size
                best_output = candidate_bytes
            if candidate_size <= self.config.max_size_bytes:
                file_path.write_bytes(candidate_bytes)
                return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.COMPRESSED_TO_TARGET, original_size, candidate_size, None, f"compressed with {setting}")
        if best_output is not None:
            file_path.write_bytes(best_output)
            return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.COMPRESSED_BUT_ABOVE_TARGET, original_size, best_size, FailureReason.PDF_COMPRESSION_FAILED, "best effort PDF compression did not reach target")
        return FileProcessResult(relative_path, FileCategory.PDF, FileStatus.FAILED, original_size, None, FailureReason.PDF_COMPRESSION_FAILED, "no PDF output produced")


def detect_ghostscript() -> str | None:
    for command in ("gswin64c", "gswin32c", "gs"):
        if shutil.which(command):
            return command
    return None


def build_pdf_compressor(config: CompressionConfig) -> NoopPdfCompressor | GhostscriptPdfCompressor:
    if config.pdf_strategy != "ghostscript":
        return NoopPdfCompressor(config)
    executable = detect_ghostscript()
    if executable is None:
        return NoopPdfCompressor(config)
    return GhostscriptPdfCompressor(config, executable)