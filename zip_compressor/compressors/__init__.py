from .image_compressor import compress_image_file
from .pdf_compressor import (
    GhostscriptPdfCompressor,
    NoopPdfCompressor,
    build_pdf_compressor,
    detect_ghostscript,
)

__all__ = [
    "GhostscriptPdfCompressor",
    "NoopPdfCompressor",
    "build_pdf_compressor",
    "compress_image_file",
    "detect_ghostscript",
]
