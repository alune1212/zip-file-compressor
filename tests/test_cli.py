from pathlib import Path

from zip_compressor.pipeline import build_argument_parser


def test_build_argument_parser_uses_expected_defaults() -> None:
    parser = build_argument_parser()
    args = parser.parse_args(["--input", "in.zip", "--output", "out.zip"])
    assert args.max_size_kb == 2000
    assert args.pdf_strategy == "none"
    assert args.png_allow_jpg is False