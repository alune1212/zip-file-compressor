# ZIP 文件内容压缩命令行工具设计

## 1. 目标

开发一个基于 Python 3.13+ 的本地命令行工具，输入一个 ZIP 压缩包后，递归处理其中的 PDF、JPG、JPEG、PNG 文件，尽量将每个支持文件压缩到指定阈值以下，默认阈值为 2000KB。处理完成后，保留原有目录结构重新生成新的 ZIP 文件，并输出清晰的处理日志与汇总结果。

本工具不只是重新打包 ZIP，而是对压缩包内部文件内容进行单文件压缩，并采用循环尝试参数的策略逐步逼近目标大小。

## 2. 范围

### 2.1 包含内容

- 接收输入 ZIP 路径、输出 ZIP 路径和单文件目标大小参数
- 将 ZIP 解压到临时目录并递归扫描全部子目录与文件
- 支持 JPG、JPEG、PNG 的真实内容压缩
- 支持 PDF 的可扩展压缩策略接口
- 保留原始目录结构后重新打包输出 ZIP
- 输出控制台日志和结构化处理汇总
- 遇到单个文件错误时继续处理其他文件
- 兼容包含中文、空格和特殊字符的文件名

### 2.2 暂不包含内容

- 不实现 Office、GIF、TIFF 等其他格式压缩
- 不默认强依赖 Ghostscript
- 不默认将 PNG 转换为 JPG
- 不提供 GUI
- 不做并行处理，优先保证实现稳定和可维护

## 3. 运行形态

项目采用包结构，既支持直接运行入口脚本，也支持模块方式执行：

```bash
python main.py --input input.zip --output output.zip --max-size-kb 2000
python -m zip_compressor --input input.zip --output output.zip --max-size-kb 2000
```

## 4. 目录结构

```text
zip-file-compressor/
├── main.py
├── requirements.txt
├── README.md
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-01-zip-compressor-design.md
├── tests/
│   ├── test_archive.py
│   ├── test_image_compressor.py
│   ├── test_pipeline.py
│   ├── test_reporter.py
│   └── test_scanner.py
└── zip_compressor/
    ├── __init__.py
    ├── __main__.py
    ├── archive.py
    ├── models.py
    ├── pipeline.py
    ├── reporter.py
    ├── scanner.py
    └── compressors/
        ├── __init__.py
        ├── image_compressor.py
        └── pdf_compressor.py
```

## 5. 命令行参数设计

### 5.1 必选参数

- `--input`
  - 输入 ZIP 文件路径
- `--output`
  - 输出 ZIP 文件路径

### 5.2 可选参数

- `--max-size-kb`
  - 单文件目标大小，默认 `2000`
- `--png-allow-jpg`
  - 是否允许 PNG 在必要时转换为 JPG，默认关闭
- `--pdf-strategy`
  - PDF 压缩策略，默认 `none`
  - 预留值：`none`、`ghostscript`
- `--log-file`
  - 可选日志文件路径
- `--min-image-side`
  - 图片最小边长阈值，默认例如 `800`
- `--min-jpeg-quality`
  - JPEG 最低质量阈值，默认例如 `35`

## 6. 模块职责

### 6.1 `main.py`

- 解析命令行参数
- 构造配置对象
- 初始化日志
- 调用主流程并打印结果摘要
- 根据成功或失败返回适当退出码

### 6.2 `zip_compressor/models.py`

- 定义配置与结果相关的数据结构
- 典型对象：
  - `CompressionConfig`
  - `DiscoveredFile`
  - `FileProcessResult`
  - `RunSummary`
  - `FailureReason`
  - `FileCategory`

### 6.3 `zip_compressor/archive.py`

- 验证输入 ZIP 是否存在且可读取
- 安全解压到临时目录，避免路径穿越
- 按原始相对路径重新打包为输出 ZIP
- 保留目录结构和文件名

### 6.4 `zip_compressor/scanner.py`

- 递归扫描解压目录下所有文件
- 根据扩展名识别文件类别
- 产出结构化文件列表
- 对不支持的类型做好记录

### 6.5 `zip_compressor/compressors/image_compressor.py`

- 处理 JPG、JPEG、PNG
- 如果原文件已满足阈值，则直接返回“无需压缩”
- 否则执行循环参数尝试
- 将最终结果写回目标路径

### 6.6 `zip_compressor/compressors/pdf_compressor.py`

- 提供 PDF 策略接口
- 默认实现：
  - `NoopPdfCompressor`：默认策略，记录 PDF 未启用压缩能力
  - `GhostscriptPdfCompressor`：如果用户选择且环境可用，则执行外部压缩
- 提供 Ghostscript 可执行命令探测逻辑

### 6.7 `zip_compressor/reporter.py`

- 配置日志格式
- 记录逐文件处理日志
- 汇总最终统计信息
- 输出失败文件及失败原因

### 6.8 `zip_compressor/pipeline.py`

- 串联主流程：
  - 创建临时目录
  - 解压
  - 扫描
  - 逐文件处理
  - 汇总结果
  - 重新打包
- 保证异常隔离和临时目录清理

## 7. 文件分类规则

扫描时按扩展名进行初步分类，忽略大小写：

- `.pdf` -> `pdf`
- `.jpg`、`.jpeg` -> `jpeg`
- `.png` -> `png`
- 其他 -> `unsupported`

分类仅用于决定处理器，最终异常仍要在处理阶段捕获。例如扩展名是 `.jpg` 但文件已损坏，仍会被识别为 JPEG，但在打开或保存时记录为损坏文件。

## 8. 主流程设计

1. 验证输入参数与输入 ZIP 路径
2. 创建临时目录
3. 安全解压 ZIP 到临时目录
4. 递归扫描全部文件并分类
5. 逐个处理已发现文件
6. 记录每个文件的结果
7. 将工作目录重新打包为输出 ZIP
8. 输出汇总报告
9. 自动清理临时目录

单个文件失败不会中断整个任务；只有 ZIP 本身无法读取、无法解压、或输出 ZIP 无法写入时，整体任务才返回失败。

## 9. 图片压缩算法设计

### 9.1 共通规则

- 任何支持图片文件在处理前先检查文件大小
- 若已小于等于目标大小：
  - 不重新编码
  - 直接记为 `already_within_target`
- 若大于目标大小：
  - 读取图片
  - 进入多轮参数尝试
  - 每次尝试后写入临时候选文件并检测大小
  - 若候选文件更小且成功达标，则采用该结果
  - 若始终未达标，则保留压缩尝试中最小的结果作为输出，并记录“未达到目标”

最后这一点是为了让用户至少得到尽可能小的版本，而不是无变化的原文件。结果汇总中会明确说明该文件未压到目标阈值。

### 9.2 JPEG 压缩策略

JPEG 的尝试分两阶段进行：

#### 第一阶段：仅调编码参数

在原始尺寸下，按一组质量阶梯循环尝试，例如：

- `95`
- `90`
- `85`
- `80`
- `75`
- `70`
- `65`
- `60`
- `55`
- `50`
- `45`
- `40`
- `35`

每轮保存时启用：

- `optimize=True`
- `progressive=True`

如果任一结果达到目标大小，则停止。

#### 第二阶段：逐步缩放尺寸并重复质量阶梯

如果第一阶段仍超限，则在保证不低于最小边长阈值的前提下，按比例逐步缩小，例如：

- `0.95`
- `0.90`
- `0.85`
- `0.80`
- `0.75`
- `0.70`
- `0.65`
- `0.60`

每个缩放比例下重新走一遍质量阶梯，直到：

- 达到目标大小
- 或图片最短边已到最小边长阈值
- 或已尝试完全部参数

### 9.3 PNG 压缩策略

PNG 分三层尝试：

#### 第一层：无损优化

- `optimize=True`
- 调整 `compress_level`
- 保持原格式输出

#### 第二层：轻度减色或模式调整

如果图片不是调色板模式，可尝试转为更省体积的模式，例如：

- 有透明通道时保留透明能力
- 无透明通道时可尝试量化颜色

此阶段的目标是尽量在较小视觉损失下缩小体积。

#### 第三层：缩放尺寸

如果仍超限，则逐步缩小分辨率，缩放阶梯与 JPEG 类似，并在每个尺寸上重新做无损或轻度有损尝试。

#### 可选第四层：转换为 JPEG

仅当 `--png-allow-jpg` 显式开启且图片不依赖透明背景时，允许尝试转成 JPEG。转换后文件扩展名将变为 `.jpg`，并更新最终打包内容中的对应路径。默认关闭此能力，避免改变用户文件格式预期。

## 10. PDF 压缩策略设计

### 10.1 默认策略

默认 `pdf_strategy=none`，即：

- 不执行真实 PDF 压缩
- 不中断整个任务
- 将 PDF 记录为“未启用可用 PDF 压缩策略”

这满足“接口先搭好、默认不强依赖 Ghostscript”的要求。

### 10.2 Ghostscript 策略

当用户显式指定 `--pdf-strategy ghostscript` 时：

- 程序尝试检测本机可执行命令
- Windows 常见命令：
  - `gswin64c`
  - `gswin32c`
- macOS/Linux 常见命令：
  - `gs`

若未检测到命令，则该 PDF 文件记录失败原因 `pdf_strategy_unavailable`。

若检测到命令，则按多档参数循环尝试，例如：

- `/printer`
- `/ebook`
- `/screen`

每轮输出候选 PDF，检测大小；达到目标则停止。若全部尝试后仍超限，则保留最小候选文件并记录为未达到目标。

### 10.3 为什么不默认依赖 Ghostscript

- Windows 环境中不一定预装
- 用户明确希望默认采用第 3 种策略
- 通过策略接口可在后续扩展更多 PDF 压缩方式，而不影响主流程结构

## 11. 结果状态设计

每个文件处理结果包含：

- 原始相对路径
- 文件类别
- 原始大小
- 输出大小
- 是否支持
- 是否原本已在阈值内
- 是否成功压到目标
- 是否发生异常
- 失败原因
- 错误详情摘要

建议状态枚举：

- `already_within_target`
- `compressed_to_target`
- `compressed_but_above_target`
- `skipped_unsupported`
- `failed`

## 12. 失败原因设计

统一使用稳定的失败原因编码，便于日志和后续扩展：

- `unsupported_type`
- `corrupted_file`
- `image_open_failed`
- `image_save_failed`
- `image_cannot_reach_target`
- `pdf_strategy_unavailable`
- `pdf_compression_failed`
- `zip_extract_error`
- `zip_pack_error`
- `unexpected_error`

其中：

- `compressed_but_above_target` 不一定属于异常，但仍要出现在失败清单中
- `failed` 表示该文件处理过程中发生错误或完全无法产生有效输出

## 13. ZIP 安全与路径处理

### 13.1 解压安全

为防止 ZIP 路径穿越，解压前对每个成员路径做校验：

- 不允许绝对路径
- 不允许包含 `..` 后跳出目标目录

不安全条目将导致整体解压失败，因为这是 ZIP 输入本身的安全问题，不属于单文件可恢复错误。

### 13.2 路径兼容

- 全程使用 `pathlib.Path`
- 打包时使用相对路径写入 ZIP
- 保证中文、空格和特殊字符按 Python 标准库路径语义处理

## 14. 日志与汇总设计

### 14.1 逐文件日志

日志示例：

- 开始解压 ZIP
- 发现文件：`docs/a.pdf`
- JPEG 尝试质量 `75`，结果 `2450KB`
- PNG 缩放到 `90%` 后结果 `1800KB`
- 跳过不支持文件：`notes/readme.txt`
- PDF 未启用策略：`reports/demo.pdf`

### 14.2 最终汇总

汇总至少包括：

- 总文件数
- 支持类型文件数
- 成功压到目标大小的文件数
- 原本就小于阈值的文件数
- 压缩后仍超限的文件数
- 跳过的不支持文件数
- 失败文件数
- 每个失败文件的原因

## 15. 测试策略

采用 TDD，优先覆盖核心行为。

### 15.1 单元测试

- `scanner.py`
  - 能递归发现多层目录文件
  - 能正确分类扩展名
- `archive.py`
  - 能安全解压和重新打包
  - 能拒绝路径穿越 ZIP
- `image_compressor.py`
  - 原本小文件直接通过
  - 大图片会进入多轮压缩尝试
  - 达标时停止
  - 不达标时返回最小结果并标记状态
- `reporter.py`
  - 能正确汇总统计数字

### 15.2 集成测试

- 构造带嵌套目录的 ZIP
- 运行主流程
- 验证输出 ZIP 结构未变
- 验证支持文件被处理
- 验证不支持文件被保留且记录为跳过

### 15.3 PDF 测试边界

- 默认策略下，PDF 被记录为策略不可用或未启用
- 不依赖本机一定安装 Ghostscript
- Ghostscript 可用性检测逻辑单独测试

## 16. 非功能设计决策

### 16.1 可维护性

- 用小模块明确划分职责
- 通过数据类统一跨模块传递状态
- 把压缩策略和主流程解耦，便于扩展

### 16.2 跨平台

- 路径、临时目录、ZIP 处理都基于标准库
- 外部依赖仅 Pillow
- PDF 压缩策略做成可选，不阻塞 Windows 用户直接使用

### 16.3 性能

- 当前版本串行处理，避免复杂并发错误
- 优先追求稳定、正确和可读性
- 后续若需提升性能，可在单文件任务层增加并发

## 17. 实现阶段的关键约束

- 先写测试，再写实现
- 不对已经满足阈值的文件重复压缩
- 不因为单个文件失败而中断整个任务
- 默认不改变 PNG 文件格式
- 默认不强依赖 Ghostscript
- 结果汇总必须清晰区分：
  - 原本已达标
  - 压缩后达标
  - 压缩后仍未达标
  - 处理失败
  - 不支持类型

## 18. 验收对照

该设计对应用户验收标准如下：

- ZIP 中所有支持类型文件都会被递归扫描和处理
- 输出 ZIP 通过相对路径打包保持原目录结构
- 图片文件采用循环参数尝试机制，尽量压缩到阈值以下
- PDF 采用可扩展策略接口，默认不强依赖外部工具
- 个别文件失败只进入失败清单，不影响整体任务
- 项目结构清晰，可本地直接运行，也便于后续扩展

