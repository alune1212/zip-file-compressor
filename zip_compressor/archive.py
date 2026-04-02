from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


def _normalize_zip_member_path(member_name: str) -> Path:
    if not member_name:
        raise ValueError("empty zip member name is not allowed")

    normalized_parts: list[str] = []
    for part in PurePosixPath(member_name).parts:
        if part == ".":
            continue
        if part == "..":
            raise ValueError(f"unsafe zip member path: {member_name!r}")
        if part in {"/", "\\"}:
            continue
        normalized_parts.append(part)

    if not normalized_parts:
        raise ValueError(f"unsafe zip member path: {member_name!r}")

    if (
        PurePosixPath(member_name).is_absolute()
        or PureWindowsPath(member_name).is_absolute()
        or member_name.startswith(("/", "\\"))
    ):
        raise ValueError(f"unsafe zip member path: {member_name!r}")

    return Path(*normalized_parts)


def _member_target_path(destination_dir: Path, member_name: str) -> Path:
    relative_path = _normalize_zip_member_path(member_name)
    target_path = destination_dir / relative_path
    destination_root = destination_dir.resolve()
    target_root = target_path.resolve(strict=False)
    if not target_root.is_relative_to(destination_root):
        raise ValueError(f"unsafe zip member path: {member_name!r}")
    return target_path


def extract_zip_to_directory(source_zip: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip) as archive:
        for info in archive.infolist():
            target_path = _member_target_path(destination_dir, info.filename)
            if info.is_dir() or info.filename.endswith("/"):
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def _write_directory_entry(archive: zipfile.ZipFile, relative_path: Path) -> None:
    directory_name = relative_path.as_posix().rstrip("/") + "/"
    archive.writestr(directory_name, b"")


def create_zip_from_directory(source_dir: Path, output_zip: Path) -> None:
    source_dir = source_dir.resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for current_dir, dirs, files in os.walk(source_dir, topdown=True, followlinks=False):
            current_path = Path(current_dir)
            dirs[:] = [
                directory_name
                for directory_name in sorted(dirs)
                if not (current_path / directory_name).is_symlink()
            ]

            for directory_name in dirs:
                directory_path = current_path / directory_name
                archive_path = directory_path.relative_to(source_dir)
                _write_directory_entry(archive, archive_path)

            for file_name in sorted(files):
                file_path = current_path / file_name
                if file_path.is_symlink() or not file_path.is_file():
                    continue
                archive_path = file_path.relative_to(source_dir)
                archive.write(file_path, archive_path.as_posix())
