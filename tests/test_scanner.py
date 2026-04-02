import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.models import FileCategory
from zip_compressor.scanner import categorize_file, scan_files


def test_categorize_file_is_case_insensitive() -> None:
    assert categorize_file(Path("report.PDF")) is FileCategory.PDF
    assert categorize_file(Path("photo.JpEg")) is FileCategory.JPEG
    assert categorize_file(Path("image.PNG")) is FileCategory.PNG


def test_scan_files_discovers_files_recursively(tmp_path: Path) -> None:
    (tmp_path / "level1").mkdir()
    (tmp_path / "level1" / "level2").mkdir()
    (tmp_path / "level1" / "level2" / "deep.pdf").write_bytes(b"pdf")
    (tmp_path / "level1" / "middle.jpg").write_bytes(b"jpg")
    (tmp_path / "root.png").write_bytes(b"png")

    discovered = scan_files(tmp_path)

    assert [item.relative_path for item in discovered] == [
        Path("level1/level2/deep.pdf"),
        Path("level1/middle.jpg"),
        Path("root.png"),
    ]


def test_scan_files_uses_relative_paths_from_root(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    file_path = tmp_path / "nested" / "sample.txt"
    file_path.write_text("text")

    discovered = scan_files(tmp_path)

    assert discovered[0].absolute_path == file_path
    assert discovered[0].relative_path == Path("nested/sample.txt")


def test_scan_files_classifies_supported_and_unsupported_types(tmp_path: Path) -> None:
    (tmp_path / "doc.PDF").write_bytes(b"pdf")
    (tmp_path / "photo.jpeg").write_bytes(b"jpg")
    (tmp_path / "graphic.png").write_bytes(b"png")
    (tmp_path / "notes.txt").write_text("text")

    discovered = scan_files(tmp_path)

    # sorted() orders by filename alphabetically: doc.PDF, graphic.png, notes.txt, photo.jpeg
    assert [item.category for item in discovered] == [
        FileCategory.PDF,
        FileCategory.PNG,
        FileCategory.UNSUPPORTED,
        FileCategory.JPEG,
    ]
