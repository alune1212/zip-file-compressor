from pathlib import Path

import pytest

from zip_compressor.compressors.pdf_compressor import (
    GhostscriptPdfCompressor,
    build_pdf_compressor,
)
from zip_compressor.models import CompressionConfig, FileCategory, FileStatus


def _create_multipage_pdf(tmp_path: Path, name: str = "test", pages: int = 2) -> Path:
    """Create a minimal valid multi-page PDF for testing."""
    pdf_path = tmp_path / f"{name}.pdf"
    # Minimal PDF with multiple pages
    content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 1) Tj ET
endstream
endobj
5 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << >> >>
endobj
6 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 2) Tj ET
endstream
endobj
xref
0 7
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000352 00000 n
0000000500 00000 n
trailer
<< /Size 7 /Root 1 0 R >>
startxref
595
%%EOF
"""
    pdf_path.write_bytes(content)
    return pdf_path


def test_pdf_force_jpg_converts_to_multiple_jpgs(tmp_path: Path):
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        pdf_strategy="ghostscript",
        force_jpg=True,
        max_size_kb=2000,
    )
    compressor = build_pdf_compressor(config)
    if not isinstance(compressor, GhostscriptPdfCompressor):
        pytest.skip("ghostscript not available")

    pdf_path = _create_multipage_pdf(tmp_path, pages=2)
    relative_path = Path("test.pdf")

    result = compressor.compress(pdf_path, relative_path)

    # Should return success with first JPG as relative_path
    assert result.status == FileStatus.SUCCESS
    assert result.category == FileCategory.JPEG
    assert result.relative_path.suffix == ".jpg"
    assert "_page_1.jpg" in result.relative_path.name

    # Original PDF should be deleted
    assert not pdf_path.exists()

    # Both page JPGs should exist
    page1_jpg = tmp_path / result.relative_path.name
    page2_jpg = tmp_path / "test_page_2.jpg"
    assert page1_jpg.exists(), f"Expected {page1_jpg} to exist"
    assert page2_jpg.exists(), f"Expected {page2_jpg} to exist"

    # Result message should indicate conversion
    assert "JPG" in result.message


def test_pdf_force_jpg_single_page(tmp_path: Path):
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        pdf_strategy="ghostscript",
        force_jpg=True,
        max_size_kb=2000,
    )
    compressor = build_pdf_compressor(config)
    if not isinstance(compressor, GhostscriptPdfCompressor):
        pytest.skip("ghostscript not available")

    pdf_path = _create_multipage_pdf(tmp_path, name="single", pages=1)
    relative_path = Path("single.pdf")

    result = compressor.compress(pdf_path, relative_path)

    assert result.status == FileStatus.SUCCESS
    assert result.category == FileCategory.JPEG
    assert "_page_1.jpg" in result.relative_path.name
    assert not pdf_path.exists()


def test_pdf_force_jpg_skips_when_ghostscript_unavailable(tmp_path: Path):
    """When ghostscript is not available, force_jpg should still use NoopPdfCompressor."""
    config = CompressionConfig(
        input_zip=tmp_path / "in.zip",
        output_zip=tmp_path / "out.zip",
        pdf_strategy="ghostscript",  # Request ghostscript
        force_jpg=True,  # But also request JPG conversion
        max_size_kb=2000,
    )
    # Force to NoopPdfCompressor by manually constructing it with no executable
    compressor = GhostscriptPdfCompressor(config, executable="nonexistent_gs")
    pdf_path = _create_multipage_pdf(tmp_path)
    relative_path = Path("test.pdf")

    result = compressor.compress(pdf_path, relative_path)

    # NoopPdfCompressor returns FAILED with PDF_STRATEGY_UNAVAILABLE
    assert result.status == FileStatus.FAILED
    assert result.category == FileCategory.PDF
    assert result.failure_reason is not None