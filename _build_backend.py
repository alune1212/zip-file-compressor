from __future__ import annotations

import base64
import csv
import hashlib
import io
from pathlib import Path
import tempfile
import tarfile
import zipfile

NAME = "zip-compressor"
NORMALIZED_NAME = "zip_compressor"
VERSION = "0.1.0"
WHEEL_TAG = "py3-none-any"
ROOT = Path(__file__).resolve().parent


def _dist_info_dir() -> str:
    return f"{NORMALIZED_NAME}-{VERSION}.dist-info"


def _metadata_text() -> str:
    return "\n".join(
        [
            "Metadata-Version: 2.3",
            f"Name: {NAME}",
            f"Version: {VERSION}",
            "Summary: ZIP content compressor",
            "",
        ]
    )


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: _build_backend",
            "Root-Is-Purelib: true",
            f"Tag: {WHEEL_TAG}",
            "",
        ]
    )


def _record_line(path: str, data: bytes) -> tuple[str, str, str]:
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return path, f"sha256={encoded}", str(len(data))


def _build_wheel_file(wheel_directory: str, editable: bool) -> str:
    wheel_name = f"{NORMALIZED_NAME}-{VERSION}-{WHEEL_TAG}.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    dist_info = _dist_info_dir()
    files: list[tuple[str, bytes]] = [
        (f"{NORMALIZED_NAME}.pth", f"{ROOT}\n".encode("utf-8")),
        (f"{dist_info}/METADATA", _metadata_text().encode("utf-8")),
        (f"{dist_info}/WHEEL", _wheel_text().encode("utf-8")),
    ]

    record_rows: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files:
            archive.writestr(path, data)
            record_rows.append(_record_line(path, data))

        record_buffer = io.StringIO()
        writer = csv.writer(record_buffer, lineterminator="\n")
        for row in record_rows:
            writer.writerow(row)
        writer.writerow((f"{dist_info}/RECORD", "", ""))
        record_data = record_buffer.getvalue().encode("utf-8")
        archive.writestr(f"{dist_info}/RECORD", record_data)

    return wheel_name


def get_requires_for_build_wheel(config_settings: dict[str, str] | None = None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings: dict[str, str] | None = None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    dist_info = Path(metadata_directory) / _dist_info_dir()
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "top_level.txt").write_text(f"{NORMALIZED_NAME}\n", encoding="utf-8")
    return dist_info.name


def prepare_metadata_for_build_editable(
    metadata_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_wheel_file(wheel_directory, editable=False)


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_wheel_file(wheel_directory, editable=True)


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, str] | None = None,
) -> str:
    archive_name = f"{NORMALIZED_NAME}-{VERSION}.tar.gz"
    sdist_path = Path(sdist_directory) / archive_name
    with tempfile.TemporaryDirectory() as temp_dir:
        staging = Path(temp_dir) / f"{NORMALIZED_NAME}-{VERSION}"
        staging.mkdir()
        (staging / "pyproject.toml").write_text((ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8")
        (staging / "requirements.txt").write_text((ROOT / "requirements.txt").read_text(encoding="utf-8"), encoding="utf-8")
        (staging / "_build_backend.py").write_text((ROOT / "_build_backend.py").read_text(encoding="utf-8"), encoding="utf-8")
        package_dir = staging / "zip_compressor"
        package_dir.mkdir()
        for source in (ROOT / "zip_compressor").glob("*.py"):
            (package_dir / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        with tarfile.open(sdist_path, "w:gz") as archive:
            archive.add(staging, arcname=staging.name)
    return archive_name
