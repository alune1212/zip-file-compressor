# ZIP File Compressor

本地命令行工具：输入一个 ZIP 压缩包，递归处理其中的 PDF、JPG、JPEG、PNG 文件，尽量将每个支持文件压缩到指定大小以下，并保持原目录结构重新生成新的 ZIP。

## 项目目录结构

```text
zip-file-compressor/
├── main.py
├── requirements.txt
├── pyproject.toml
├── zip_compressor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── archive.py
│   ├── models.py
│   ├── pipeline.py
│   ├── reporter.py
│   ├── scanner.py
│   └── compressors/
│       ├── __init__.py
│       ├── image_compressor.py
│       └── pdf_compressor.py
└── tests/
    ├── test_archive.py
    ├── test_cli.py
    ├── test_force_jpg_integration.py
    ├── test_image_compressor.py
    ├── test_image_compressor_force_jpg.py
    ├── test_models.py
    ├── test_pdf_compressor.py
    ├── test_pdf_compressor_force_jpg.py
    ├── test_pipeline.py
    ├── test_reporter.py
    └── test_scanner.py
```

## 功能范围

- ZIP：解压到临时目录，处理后重新打包，保留原始目录结构，执行结束自动清理临时目录。
- JPG/JPEG：循环尝试质量和缩放参数，使用 Pillow 的 `optimize` 重新编码，直到达到目标大小或触及质量/分辨率阈值。
- PNG：优先 PNG 重新编码和缩放；可通过 `--png-allow-jpg` 允许非透明 PNG 转 JPG。若同目录已有同名 `.jpg`，会自动禁用该 PNG 的转 JPG，避免覆盖文件。
- 强制 JPG：可通过 `--force-jpg` 对需要处理的 PNG 强制输出 JPG；遇到同名 JPG 时会生成唯一文件名，避免覆盖原文件。当前实现不会把 PDF 转成 JPG，也不会把已有 `.jpeg` 统一改名为 `.jpg`。
- PDF：默认不启用压缩策略；使用 `--pdf-strategy ghostscript` 后调用本机 Ghostscript，按 `/printer`、`/ebook`、`/screen` 多档参数循环尝试压缩 PDF。
- 异常处理：不支持类型会跳过并记录；损坏文件或单文件压缩失败不会中断整个 ZIP 任务，会进入失败清单。

## 安装

建议使用 Python 3.13+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

按需求示例运行：

```bash
python main.py --input input.zip --output output.zip --max-size-kb 2000
```

也可以使用模块入口：

```bash
python -m zip_compressor --input input.zip --output output.zip --max-size-kb 2000
```

常用参数：

```bash
python main.py \
  --input input.zip \
  --output output.zip \
  --max-size-kb 2000 \
  --png-allow-jpg \
  --force-jpg \
  --pdf-strategy ghostscript \
  --log-file run.log
```

参数说明：

- `--input`：源 ZIP 文件路径，必填。
- `--output`：输出 ZIP 文件路径，必填。
- `--max-size-kb`：单文件目标大小，默认 `2000`。
- `--png-allow-jpg`：允许无透明通道 PNG 在必要时转为 JPG，默认不允许。
- `--force-jpg`：强制需要处理的 PNG 输出为 JPG，默认不启用；不覆盖 PDF 转 JPG。
- `--pdf-strategy`：PDF 压缩策略，支持 `none`、`ghostscript`，默认 `none`。
- `--log-file`：可选日志文件路径，日志使用 UTF-8。
- `--min-image-side`：图片缩放后的最小边长，默认 `800`。
- `--min-jpeg-quality`：JPEG 迭代压缩最低质量，默认 `35`。

## Ghostscript

PDF 压缩依赖本机 Ghostscript。未安装或未启用时，PDF 文件会记录为失败项，但不会中断 ZIP 中其他文件处理。

当前仓库内的 Ghostscript 路径只做 PDF 压缩，不做 PDF 页面渲染到 JPG。若业务要求“输入 ZIP 内的 PDF 全部输出为 JPG”，需要先安装并实现 PDF 渲染策略，或使用仓库外工具链单独转换后再打包。

Windows 安装方式：

1. 打开 Ghostscript 官方下载页：https://www.ghostscript.com/releases/gsdnld.html
2. 下载并安装 Windows 64-bit 版本。
3. 确认安装目录的 `bin` 路径已加入 `PATH`，常见路径类似 `C:\Program Files\gs\gs10.xx.x\bin`。
4. 重新打开 PowerShell 或 CMD 后执行检测命令。

检测命令：

```powershell
gswin64c --version
```

如果是 32 位安装包：

```powershell
gswin32c --version
```

macOS/Linux 通常检测：

```bash
gs --version
```

代码会按 `gswin64c`、`gswin32c`、`gs` 的顺序自动检测可执行命令。

## 输出结果

CLI 会输出汇总：

- 总文件数
- 支持类型文件数
- 成功压缩到目标大小的文件数
- 原本已小于等于阈值的文件数
- 压缩后仍超限的文件数
- 跳过不支持类型的文件数
- 压缩失败文件数
- 每个失败文件的路径、失败原因和错误信息

## 测试

如果使用现有虚拟环境：

```bash
.venv/bin/python -m pytest -q
```

如果使用 uv：

```bash
uv run pytest -q
```

2026-05-08 在当前 checkout 验证结果：`.venv/bin/python -m pytest -q` -> `62 passed, 2 skipped`。2 个 skipped 测试依赖本机 Ghostscript。
