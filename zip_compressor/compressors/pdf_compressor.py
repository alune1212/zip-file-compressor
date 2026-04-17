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

        # Handle force_jpg=True: convert PDF pages to JPEG images
        if self.config.force_jpg:
            return self._convert_pdf_to_jpg(file_path, relative_path, original_size)

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

    def _convert_pdf_to_jpg(self, file_path: Path, relative_path: Path, original_size: int) -> FileProcessResult:
        """Convert PDF pages to JPEG images using Ghostscript."""
        stem = file_path.stem
        output_pattern = file_path.parent / f"{stem}_page_%d.jpg"
        command = [
            self.executable,
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=jpeg",
            "-r150",
            "-dJPEGQ=85",
            f"-sOutputFile={output_pattern}",
            str(file_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Clean up any orphaned JPG files that gs might have produced
            for orphaned in file_path.parent.glob(f"{stem}_page_*.jpg"):
                orphaned.unlink(missing_ok=True)
            return FileProcessResult(
                relative_path,
                FileCategory.PDF,
                FileStatus.FAILED,
                original_size,
                None,
                FailureReason.PDF_COMPRESSION_FAILED,
                "ghostscript failed to convert PDF to JPG",
            )

        # Find generated JPG files
        jpg_files = sorted(file_path.parent.glob(f"{stem}_page_*.jpg"))
        if not jpg_files:
            return FileProcessResult(
                relative_path,
                FileCategory.PDF,
                FileStatus.FAILED,
                original_size,
                None,
                FailureReason.PDF_COMPRESSION_FAILED,
                "no JPG files produced from PDF",
            )

        # Calculate total size of all JPG files
        total_jpg_size = sum(f.stat().st_size for f in jpg_files)
        first_jpg_relative = relative_path.parent / jpg_files[0].name

        result = FileProcessResult(
            first_jpg_relative,
            FileCategory.JPEG,
            FileStatus.SUCCESS,
            original_size,
            total_jpg_size,
            None,
            f"PDF converted to {len(jpg_files)} JPG pages",
        )

        # Delete original PDF only after confirming conversion was successful
        file_path.unlink(missing_ok=True)

        return result


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