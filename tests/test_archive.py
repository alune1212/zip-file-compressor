import zipfile
from pathlib import Path

import pytest

from zip_compressor.archive import create_zip_from_directory, extract_zip_to_directory


def test_extract_zip_to_directory_restores_nested_files(tmp_path: Path) -> None:
    source_zip = tmp_path / "source.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("nested/file.txt", "payload")

    destination = tmp_path / "out"
    extract_zip_to_directory(source_zip, destination)

    assert (destination / "nested" / "file.txt").read_text(encoding="utf-8") == "payload"


def test_extract_zip_to_directory_rejects_path_traversal(tmp_path: Path) -> None:
    source_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("../evil.txt", "bad")

    with pytest.raises(ValueError, match="Unsafe ZIP member path"):
        extract_zip_to_directory(source_zip, tmp_path / "out")


def test_create_zip_from_directory_preserves_relative_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    nested = root / "dir"
    nested.mkdir()
    (nested / "file.txt").write_text("ok", encoding="utf-8")
    output_zip = tmp_path / "result.zip"

    create_zip_from_directory(root, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        assert archive.namelist() == ["dir/file.txt"]