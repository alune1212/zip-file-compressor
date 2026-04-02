# ZIP File Compressor

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python main.py --input input.zip --output output.zip --max-size-kb 2000
python -m zip_compressor --input input.zip --output output.zip --max-size-kb 2000
```

## Ghostscript on Windows

1. Download and install Ghostscript from the official installer.
2. Make sure `gswin64c.exe` or `gswin32c.exe` is on `PATH`.
3. Verify with:

```powershell
gswin64c -version
```