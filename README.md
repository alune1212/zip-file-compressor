# ZIP 文件压缩器

一款本地 CLI 工具，可解压 ZIP 压缩包、递归压缩支持的 PDF/JPG/JPEG/PNG 文件至目标大小、保留目录结构，并输出新的 ZIP 文件及日志和汇总报告。

## 功能特性

- **递归扫描** - 发现嵌套目录中的所有支持的文件
- **JPEG 压缩** - 通过迭代质量和缩放达到目标大小
- **PNG 优化** - 压缩级别和调色板 reduction
- **PNG 转 JPEG** - 可选将不透明 PNG 转换为 JPEG
- **PDF 压缩** - 基于 Ghostscript 的压缩策略（可选）
- **路径遍历保护** - 安全解压不受信任的 ZIP 文件
- **汇总报告** - 每个文件的处理状态和失败详情

## 安装

```bash
# 克隆仓库
git clone https://github.com/alune1212/zip-file-compressor.git
cd zip-file-compressor

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

```bash
# 基本用法
python main.py --input input.zip --output output.zip

# 自定义大小限制（单位：KB）
python main.py --input input.zip --output output.zip --max-size-kb 1500

# 启用 PNG 转 JPEG 转换（适用于不透明图片）
python main.py --input input.zip --output output.zip --png-allow-jpg

# 启用 PDF 压缩（需要安装 Ghostscript）
python main.py --input input.zip --output output.zip --pdf-strategy ghostscript

# 保存日志到文件
python main.py --input input.zip --output output.zip --log-file compressor.log

# 通过模块执行
python -m zip_compressor --input input.zip --output output.zip
```

## CLI 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--input` | （必填） | 输入 ZIP 文件路径 |
| `--output` | （必填） | 输出 ZIP 文件路径 |
| `--max-size-kb` | 2000 | 目标文件最大大小（KB） |
| `--png-allow-jpg` | False | 将不透明 PNG 转换为 JPEG |
| `--pdf-strategy` | none | PDF 压缩策略：`none` 或 `ghostscript` |
| `--log-file` | None | 日志文件路径 |
| `--min-image-side` | 800 | 图片最小边长（像素） |
| `--min-jpeg-quality` | 35 | 最小 JPEG 质量（1-100） |

## 系统要求

- Python 3.9+
- Pillow

### PDF 压缩（可选）

**macOS/Linux：**
```bash
# 通过 Homebrew 安装
brew install ghostscript

# 验证安装
gs -version
```

**Windows：**
1. 从 https://www.ghostscript.com/download/gsdnld.html 下载 Ghostscript
2. 安装并将 `gswin64c.exe` 添加到 PATH
3. 验证：
```powershell
gswin64c -version
```

## 项目结构

```
zip_compressor/
├── __init__.py          # 包入口
├── __main__.py          # 模块入口点
├── models.py            # 数据模型（CompressionConfig、FileProcessResult 等）
├── scanner.py           # 递归文件发现和分类
├── archive.py           # ZIP 解压和打包
├── reporter.py          # 汇总聚合和日志
├── pipeline.py          # 主编排和 CLI
└── compressors/
    ├── __init__.py
    ├── image_compressor.py  # JPEG/PNG 压缩逻辑
    └── pdf_compressor.py     # PDF 策略接口
```

## 退出码

- `0` - 成功（所有文件处理完成，无失败）
- `1` - 部分成功（部分文件失败或超过目标大小）

## 许可证

MIT