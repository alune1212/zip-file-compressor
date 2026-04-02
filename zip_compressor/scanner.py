import os
from pathlib import Path

from zip_compressor.models import DiscoveredFile, FileCategory


def categorize_file(path: Path) -> FileCategory:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return FileCategory.PDF
    if suffix in {".jpg", ".jpeg"}:
        return FileCategory.JPEG
    if suffix == ".png":
        return FileCategory.PNG
    return FileCategory.UNSUPPORTED


def scan_files(root_dir: Path) -> list[DiscoveredFile]:
    root_dir = root_dir.resolve()
    discovered: list[DiscoveredFile] = []
    for current_dir, dirs, files in os.walk(root_dir, topdown=True, followlinks=False):
        current_path = Path(current_dir)
        dirs[:] = [
            directory_name
            for directory_name in sorted(dirs)
            if not (current_path / directory_name).is_symlink()
        ]
        for file_name in sorted(files):
            file_path = current_path / file_name
            if file_path.is_symlink() or not file_path.is_file():
                continue
            discovered.append(
                DiscoveredFile(
                    absolute_path=file_path.resolve(),
                    relative_path=file_path.relative_to(root_dir),
                    category=categorize_file(file_path),
                    size_bytes=file_path.stat().st_size,
                )
            )
    return discovered
