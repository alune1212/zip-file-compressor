from pathlib import Path

from .models import DiscoveredFile, FileCategory


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
    for path in sorted(root_dir.rglob("*")):
        if not path.is_file():
            continue
        discovered.append(
            DiscoveredFile(
                absolute_path=path,
                relative_path=path.relative_to(root_dir),
                category=categorize_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return discovered