from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from zip_compressor.models import (
    CompressionConfig,
    FailureReason,
    FileCategory,
    FileProcessResult,
    FileStatus,
)

_GHOSTSCRIPT_COMMANDS = ("gswin64c", "gswin32c", "gs")
_PDFSETTINGS_PRESETS = ("/printer", "/ebook", "/screen")


def detect_ghostscript() -> str | None:
    for command in _GHOSTSCRIPT_COMMANDS:
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return None


def build_pdf_compressor(config: CompressionConfig) -> NoopPdfCompressor | GhostscriptPdfCompressor:
    if config.pdf_strategy != "ghostscript":
        return NoopPdfCompressor(
            failure_reason=FailureReason.PDF_STRATEGY_DISABLED,
            message="pdf compression strategy is disabled",
        )

    executable = detect_ghostscript()
    if executable is None:
        return NoopPdfCompressor(
            failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
            message="ghostscript requested but no executable was detected",
        )

    return GhostscriptPdfCompressor(config=config, executable=executable)


@dataclass(slots=True)
class NoopPdfCompressor:
    failure_reason: FailureReason = FailureReason.PDF_STRATEGY_DISABLED
    message: str = "pdf compression strategy is disabled"

    def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
        original_size = file_path.stat().st_size
        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PDF,
            status=FileStatus.FAILED,
            original_size_bytes=original_size,
            final_size_bytes=None,
            failure_reason=self.failure_reason,
            message=self.message,
        )


@dataclass(slots=True)
class GhostscriptPdfCompressor:
    config: CompressionConfig
    executable: str

    def compress(self, file_path: Path, relative_path: Path) -> FileProcessResult:
        original_size = file_path.stat().st_size
        if original_size <= self.config.max_size_bytes:
            return FileProcessResult(
                relative_path=relative_path,
                category=FileCategory.PDF,
                status=FileStatus.ALREADY_WITHIN_TARGET,
                original_size_bytes=original_size,
                final_size_bytes=original_size,
                failure_reason=None,
                message="pdf already within target size",
            )

        best_bytes: bytes | None = None
        best_preset: str | None = None
        reached_target = False

        for preset in _PDFSETTINGS_PRESETS:
            result = self._run_ghostscript(file_path, preset)
            if result.failure_message is not None:
                return FileProcessResult(
                    relative_path=relative_path,
                    category=FileCategory.PDF,
                    status=FileStatus.FAILED,
                    original_size_bytes=original_size,
                    final_size_bytes=None,
                    failure_reason=FailureReason.PDF_COMPRESSION_FAILED,
                    message=result.failure_message,
                )

            if result.returncode != 0:
                return FileProcessResult(
                    relative_path=relative_path,
                    category=FileCategory.PDF,
                    status=FileStatus.FAILED,
                    original_size_bytes=original_size,
                    final_size_bytes=None,
                    failure_reason=FailureReason.PDF_COMPRESSION_FAILED,
                    message=f"ghostscript failed for {preset}: {result.stderr.strip() or result.stdout.strip() or 'unknown error'}",
                )

            if result.output_bytes is None:
                return FileProcessResult(
                    relative_path=relative_path,
                    category=FileCategory.PDF,
                    status=FileStatus.FAILED,
                    original_size_bytes=original_size,
                    final_size_bytes=None,
                    failure_reason=FailureReason.PDF_COMPRESSION_FAILED,
                    message=f"ghostscript did not produce output for {preset}",
                )

            candidate_bytes = result.output_bytes
            if best_bytes is None or len(candidate_bytes) < len(best_bytes):
                best_bytes = candidate_bytes
                best_preset = preset
                reached_target = len(candidate_bytes) <= self.config.max_size_bytes

            if reached_target:
                break

        if best_bytes is None or len(best_bytes) >= original_size:
            return FileProcessResult(
                relative_path=relative_path,
                category=FileCategory.PDF,
                status=FileStatus.FAILED,
                original_size_bytes=original_size,
                final_size_bytes=None,
                failure_reason=FailureReason.PDF_COMPRESSION_FAILED,
                message="ghostscript did not produce a smaller pdf",
            )

        try:
            _atomic_write_bytes(file_path, best_bytes)
        except OSError as exc:
            return FileProcessResult(
                relative_path=relative_path,
                category=FileCategory.PDF,
                status=FileStatus.FAILED,
                original_size_bytes=original_size,
                final_size_bytes=None,
                failure_reason=FailureReason.PDF_COMPRESSION_FAILED,
                message=f"failed to write compressed pdf: {exc}",
            )

        final_size = len(best_bytes)

        if final_size <= self.config.max_size_bytes:
            return FileProcessResult(
                relative_path=relative_path,
                category=FileCategory.PDF,
                status=FileStatus.COMPRESSED_TO_TARGET,
                original_size_bytes=original_size,
                final_size_bytes=final_size,
                failure_reason=None,
                message=f"pdf compressed to target using {best_preset}",
            )

        return FileProcessResult(
            relative_path=relative_path,
            category=FileCategory.PDF,
            status=FileStatus.COMPRESSED_BUT_ABOVE_TARGET,
            original_size_bytes=original_size,
            final_size_bytes=final_size,
            failure_reason=FailureReason.PDF_CANNOT_REACH_TARGET,
            message=f"pdf compressed but remained above target using {best_preset}",
        )

    def _run_ghostscript(self, file_path: Path, preset: str) -> _GhostscriptRunResult:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / file_path.name
            try:
                completed = subprocess.run(
                    [
                        self.executable,
                        "-sDEVICE=pdfwrite",
                        "-dCompatibilityLevel=1.4",
                        "-dNOPAUSE",
                        "-dQUIET",
                        "-dBATCH",
                        f"-dPDFSETTINGS={preset}",
                        f"-sOutputFile={output_path}",
                        str(file_path),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except OSError as exc:
                return _GhostscriptRunResult(
                    returncode=None,
                    stdout="",
                    stderr="",
                    output_bytes=None,
                    failure_message=f"failed to launch ghostscript for {preset}: {exc}",
                )

            try:
                output_bytes = output_path.read_bytes() if output_path.exists() else None
            except OSError as exc:
                return _GhostscriptRunResult(
                    returncode=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    output_bytes=None,
                    failure_message=f"failed to read ghostscript output for {preset}: {exc}",
                )

        return _GhostscriptRunResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            output_bytes=output_bytes,
            failure_message=None,
        )


@dataclass(slots=True)
class _GhostscriptRunResult:
    returncode: int | None
    stdout: str
    stderr: str
    output_bytes: bytes | None
    failure_message: str | None = None


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=path.parent) as temp_file:
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        temp_path.replace(path)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
