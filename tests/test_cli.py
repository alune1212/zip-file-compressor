import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zip_compressor.__main__ import main


def test_cli_runs_pipeline_and_prints_summary(tmp_path: Path, capsys) -> None:
    input_zip = tmp_path / "input.zip"
    output_zip = tmp_path / "output.zip"

    with zipfile.ZipFile(input_zip, "w") as archive:
        archive.writestr("目录/readme.txt", "unsupported file")

    exit_code = main(
        [
            "--input",
            str(input_zip),
            "--output",
            str(output_zip),
            "--max-size-kb",
            "2000",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_zip.exists()
    assert "处理完成" in captured.out
    assert "总文件数: 1" in captured.out
    assert "跳过不支持类型: 1" in captured.out

    with zipfile.ZipFile(output_zip) as archive:
        assert "目录/readme.txt" in set(archive.namelist())
