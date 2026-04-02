from pathlib import Path
import zipfile


def _validate_zip_member(member_name: str, destination_dir: Path) -> Path:
    target_path = destination_dir / member_name
    resolved_target = target_path.resolve()
    resolved_destination = destination_dir.resolve()
    if not str(resolved_target).startswith(str(resolved_destination)):
        raise ValueError(f"Unsafe ZIP member path: {member_name}")
    return target_path


def extract_zip_to_directory(source_zip: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip, "r") as archive:
        for member in archive.infolist():
            target_path = _validate_zip_member(member.filename, destination_dir)
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as input_handle, target_path.open("wb") as output_handle:
                output_handle.write(input_handle.read())


def create_zip_from_directory(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())