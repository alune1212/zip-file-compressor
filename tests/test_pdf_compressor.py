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
    assert compressor.failure_reason is FailureReason.PDF_STRATEGY_DISABLED


def test_noop_pdf_compressor_returns_strategy_reason_from_instance(tmp_path: Path) -> None:
    from zip_compressor.compressors.pdf_compressor import NoopPdfCompressor

    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")

    result = NoopPdfCompressor(
        failure_reason=FailureReason.PDF_STRATEGY_UNAVAILABLE,
        message="ghostscript requested but not installed",
    ).compress(file_path, Path("sample.pdf"))

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE
    assert result.final_size_bytes is None
    assert result.message == "ghostscript requested but not installed"


def test_build_pdf_compressor_returns_unavailable_noop_when_ghostscript_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zip_compressor.compressors.pdf_compressor import NoopPdfCompressor, build_pdf_compressor
    import zip_compressor.compressors.pdf_compressor as pdf_compressor

    monkeypatch.setattr(pdf_compressor, "detect_ghostscript", lambda: None)

    compressor = build_pdf_compressor(_build_config(tmp_path, pdf_strategy="ghostscript"))

    assert isinstance(compressor, NoopPdfCompressor)
    assert compressor.failure_reason is FailureReason.PDF_STRATEGY_UNAVAILABLE
    assert "ghostscript" in compressor.message.lower()


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


def test_ghostscript_pdf_compressor_returns_compressed_to_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zip_compressor.compressors.pdf_compressor import GhostscriptPdfCompressor
    import zip_compressor.compressors.pdf_compressor as pdf_compressor

    file_path = tmp_path / "large.pdf"
    original_bytes = b"x" * 5_000
    file_path.write_bytes(original_bytes)
    config = _build_config(tmp_path, max_size_kb=2, pdf_strategy="ghostscript")

    monkeypatch.setattr(
        GhostscriptPdfCompressor,
        "_run_ghostscript",
        lambda self, file_path, preset: pdf_compressor._GhostscriptRunResult(
            returncode=0,
            stdout="",
            stderr="",
            output_bytes=b"y" * 1_500 if preset == "/ebook" else b"z" * 3_000,
        ),
    )

    result = GhostscriptPdfCompressor(config=config, executable="gs").compress(
        file_path, Path("large.pdf")
    )

    assert result.status is FileStatus.COMPRESSED_TO_TARGET
    assert result.failure_reason is None
    assert result.final_size_bytes == 1_500
    assert file_path.read_bytes() == b"y" * 1_500


def test_ghostscript_pdf_compressor_returns_above_target_when_only_best_effort_possible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zip_compressor.compressors.pdf_compressor import GhostscriptPdfCompressor
    import zip_compressor.compressors.pdf_compressor as pdf_compressor

    file_path = tmp_path / "large.pdf"
    file_path.write_bytes(b"x" * 8_000)
    config = _build_config(tmp_path, max_size_kb=2, pdf_strategy="ghostscript")

    monkeypatch.setattr(
        GhostscriptPdfCompressor,
        "_run_ghostscript",
        lambda self, file_path, preset: pdf_compressor._GhostscriptRunResult(
            returncode=0,
            stdout="",
            stderr="",
            output_bytes={
                "/printer": b"a" * 6_000,
                "/ebook": b"b" * 4_000,
                "/screen": b"c" * 3_000,
            }[preset],
        ),
    )

    result = GhostscriptPdfCompressor(config=config, executable="gs").compress(
        file_path, Path("large.pdf")
    )

    assert result.status is FileStatus.COMPRESSED_BUT_ABOVE_TARGET
    assert result.failure_reason is FailureReason.PDF_CANNOT_REACH_TARGET
    assert result.final_size_bytes == 3_000
    assert file_path.read_bytes() == b"c" * 3_000


def test_ghostscript_pdf_compressor_returns_failed_when_subprocess_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zip_compressor.compressors.pdf_compressor import GhostscriptPdfCompressor
    import zip_compressor.compressors.pdf_compressor as pdf_compressor

    file_path = tmp_path / "broken.pdf"
    original_bytes = b"x" * 5_000
    file_path.write_bytes(original_bytes)
    config = _build_config(tmp_path, max_size_kb=2, pdf_strategy="ghostscript")

    monkeypatch.setattr(
        GhostscriptPdfCompressor,
        "_run_ghostscript",
        lambda self, file_path, preset: pdf_compressor._GhostscriptRunResult(
            returncode=1,
            stdout="",
            stderr="failed to run",
            output_bytes=None,
        ),
    )

    result = GhostscriptPdfCompressor(config=config, executable="gs").compress(
        file_path, Path("broken.pdf")
    )

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.PDF_COMPRESSION_FAILED
    assert result.final_size_bytes is None
    assert file_path.read_bytes() == original_bytes


def test_ghostscript_pdf_compressor_returns_failed_when_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from zip_compressor.compressors.pdf_compressor import GhostscriptPdfCompressor
    import zip_compressor.compressors.pdf_compressor as pdf_compressor

    file_path = tmp_path / "replace.pdf"
    original_bytes = b"x" * 5_000
    file_path.write_bytes(original_bytes)
    config = _build_config(tmp_path, max_size_kb=2, pdf_strategy="ghostscript")

    monkeypatch.setattr(
        GhostscriptPdfCompressor,
        "_run_ghostscript",
        lambda self, file_path, preset: pdf_compressor._GhostscriptRunResult(
            returncode=0,
            stdout="",
            stderr="",
            output_bytes=b"y" * 1_500,
        ),
    )

    def fake_atomic_write(path: Path, data: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(pdf_compressor, "_atomic_write_bytes", fake_atomic_write)

    result = GhostscriptPdfCompressor(config=config, executable="gs").compress(
        file_path, Path("replace.pdf")
    )

    assert result.status is FileStatus.FAILED
    assert result.failure_reason is FailureReason.PDF_COMPRESSION_FAILED
    assert result.final_size_bytes is None
    assert "disk full" in result.message
    assert file_path.read_bytes() == original_bytes
