import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.models import CompressionConfig, FailureReason, FileStatus


def _build_config(tmp_path: Path, *, max_size_kb: int = 100, pdf_strategy: str = "none") -> CompressionConfig:
    return CompressionConfig(
        input_zip=tmp_path / "input.zip",
        output_zip=tmp_path / "output.zip",
        max_size_kb=max_size_kb,
        pdf_strategy=pdf_strategy,
    )


def test_build_pdf_compressor_defaults_to_noop(tmp_path: Path) -> None:
    from zip_compressor.compressors.pdf_compressor import NoopPdfCompressor, build_pdf_compressor

    compressor = build_pdf_compressor(_build_config(tmp_path))

    assert isinstance(compressor, NoopPdfCompressor)


def test_noop_pdf_compressor_returns_strategy_unavailable(tmp_path: Path) -> None:
    from zip_compressor.compressors.pdf_compressor import NoopPdfCompressor

    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    result = NoopPdfCompressor().compress(file_path, Path("sample.pdf"))

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE
    assert result.final_size_bytes is None


def test_detect_ghostscript_prefers_windows_64_then_32_then_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import zip_compressor.compressors.pdf_compressor as pdf_compressor

    commands_seen: list[str] = []
    resolved = {"gswin32c": "C:/gs/gswin32c.exe", "gs": "/usr/bin/gs"}

    def fake_which(command: str) -> str | None:
        commands_seen.append(command)
        return resolved.get(command)

    monkeypatch.setattr(pdf_compressor.shutil, "which", fake_which)

    detected = pdf_compressor.detect_ghostscript()

    assert detected == "C:/gs/gswin32c.exe"
    assert commands_seen == ["gswin64c", "gswin32c"]


def test_ghostscript_pdf_compressor_returns_already_within_target_for_small_file(
    tmp_path: Path,
) -> None:
    from zip_compressor.compressors.pdf_compressor import GhostscriptPdfCompressor

    file_path = tmp_path / "small.pdf"
    file_path.write_bytes(b"%PDF-1.4\nsmall file\n")
    config = _build_config(tmp_path, max_size_kb=10, pdf_strategy="ghostscript")

    result = GhostscriptPdfCompressor(config=config, executable="gs").compress(
        file_path, Path("small.pdf")
    )

    assert result.status is FileStatus.ALREADY_WITHIN_TARGET
    assert result.failure_reason is None
    assert result.final_size_bytes == file_path.stat().st_size
