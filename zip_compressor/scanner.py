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
    discovered: list[DiscoveredFile] = []
    for file_path in sorted(
        (path for path in root_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root_dir).as_posix(),
    ):
        discovered.append(
            DiscoveredFile(
                absolute_path=file_path.resolve(),
                relative_path=file_path.relative_to(root_dir),
                category=categorize_file(file_path),
                size_bytes=file_path.stat().st_size,
            )
        )
    return discovered
