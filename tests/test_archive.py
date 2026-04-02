import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.archive import create_zip_from_directory, extract_zip_to_directory


def test_extract_zip_to_directory_restores_nested_files(tmp_path: Path) -> None:
    source_zip = tmp_path / "source.zip"
    destination_dir = tmp_path / "output"

    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("level1/level2/deep.txt", "deep content")
        archive.writestr("root.txt", "root content")

    extract_zip_to_directory(source_zip, destination_dir)

    assert (destination_dir / "level1" / "level2" / "deep.txt").read_text() == "deep content"
    assert (destination_dir / "root.txt").read_text() == "root content"


def test_extract_zip_to_directory_rejects_path_traversal(tmp_path: Path) -> None:
    source_zip = tmp_path / "evil.zip"
    destination_dir = tmp_path / "output"

    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("../evil.txt", "nope")

    with pytest.raises(ValueError):
        extract_zip_to_directory(source_zip, destination_dir)

    assert not (tmp_path / "evil.txt").exists()


def test_extract_zip_to_directory_rejects_windows_style_path_traversal(tmp_path: Path) -> None:
    source_zip = tmp_path / "evil_windows.zip"
    destination_dir = tmp_path / "output"

    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("..\\evil.txt", "nope")

    with pytest.raises(ValueError):
        extract_zip_to_directory(source_zip, destination_dir)


@pytest.mark.parametrize("member_name", ["/evil.txt", "\\evil.txt", "C:/abs/evil.txt"])
def test_extract_zip_to_directory_rejects_absolute_paths(
    tmp_path: Path,
    member_name: str,
) -> None:
    source_zip = tmp_path / "absolute.zip"
    destination_dir = tmp_path / "output"

    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr(member_name, "nope")

    with pytest.raises(ValueError):
        extract_zip_to_directory(source_zip, destination_dir)


def test_create_zip_from_directory_uses_relative_paths(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_zip = tmp_path / "output.zip"

    (source_dir / "nested" / "deeper").mkdir(parents=True)
    (source_dir / "nested" / "deeper" / "file.txt").write_text("hello")
    (source_dir / "中文 文件.txt").write_text("world")

    create_zip_from_directory(source_dir, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        assert sorted(archive.namelist()) == [
            "nested/",
            "nested/deeper/",
            "nested/deeper/file.txt",
            "中文 文件.txt",
        ]
        assert archive.read("nested/deeper/file.txt") == b"hello"
        assert archive.read("中文 文件.txt") == b"world"


def test_create_zip_from_directory_preserves_empty_directories(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_zip = tmp_path / "output.zip"

    (source_dir / "empty" / "child").mkdir(parents=True)
    (source_dir / "nested").mkdir()
    (source_dir / "nested" / "file.txt").write_text("content")

    create_zip_from_directory(source_dir, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        assert "empty/" in archive.namelist()
        assert "empty/child/" in archive.namelist()
        assert "nested/file.txt" in archive.namelist()


def test_create_zip_from_directory_raises_when_source_missing(tmp_path: Path) -> None:
    source_dir = tmp_path / "missing"
    output_zip = tmp_path / "output.zip"

    with pytest.raises(FileNotFoundError):
        create_zip_from_directory(source_dir, output_zip)


def test_create_zip_from_directory_rejects_non_directory_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source.txt"
    output_zip = tmp_path / "output.zip"

    source_dir.write_text("not a directory")

    with pytest.raises(NotADirectoryError):
        create_zip_from_directory(source_dir, output_zip)


def test_create_zip_from_directory_skips_output_zip_inside_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_zip = source_dir / "out.zip"

    (source_dir / "nested").mkdir(parents=True)
    (source_dir / "nested" / "file.txt").write_text("content")

    create_zip_from_directory(source_dir, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        assert sorted(archive.namelist()) == ["nested/", "nested/file.txt"]
        assert "out.zip" not in archive.namelist()


def test_create_zip_from_directory_skips_symlinks(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_zip = tmp_path / "output.zip"

    (source_dir / "nested").mkdir(parents=True)
    (source_dir / "nested" / "real.txt").write_text("real")

    try:
        (source_dir / "linked.txt").symlink_to(source_dir / "nested" / "real.txt")
        (source_dir / "linked-dir").symlink_to(source_dir / "nested", target_is_directory=True)
    except (AttributeError, NotImplementedError, OSError):
        pytest.skip("symlinks are not supported on this platform")

    create_zip_from_directory(source_dir, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        assert "nested/real.txt" in archive.namelist()
        assert "linked.txt" not in archive.namelist()
        assert "linked-dir/" not in archive.namelist()
