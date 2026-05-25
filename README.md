# FileMind

AI 驱动的智能文件管理 Agent。自动扫描、分析、分类、重命名和整理电脑中的文件。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 核心能力

- **内容识别** — 提取 PDF 文本、OCR 识别图片、读取文本文件，识别发票/合同/简历/论文等文档类型
- **三维分析** — 评估文件价值（高/中/低）、推断用途（工作/学习/个人/临时）、评估操作风险
- **智能分类** — 12 种文件类型自动识别（图片/视频/文档/代码/安装包等）
- **智能重命名** — 三种策略：清理垃圾后缀 / 日期前缀 / 保留原名，分类感知命名
- **重复检测** — MD5 精确匹配 + 感知哈希相似图片 + 视频帧比对
- **时间归档** — 按年/月子目录自动归档
- **MCP Server** — 内置 MCP 协议服务器，可接入 Claude 等 AI Agent
- **操作审计** — 每次操作自动记录，支持一键撤销
- **安全第一** — 不删除任何文件，重复文件移到 `Duplicates/`，危险操作需确认

## 安装

```bash
git clone https://github.com/luoli2005/FileMind.git
cd FileMind
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> 可选依赖：`ffmpeg` / `ffprobe`（视频分析）、`tesseract`（OCR 识别）

## 使用

### Agent 模式（推荐）

```bash
python -m filemind agent ~/Downloads
```

Agent 模式全流程：扫描 → 内容识别 → 三维分析 → 生成策略 → 交互菜单 → 确认执行 → 审计报告

交互菜单提供 5 个选项：
1. **完整整理** — 分类 + 重命名 + 去重，一步到位
2. **Dry Run 预览** — 只看方案不动文件
3. **仅重命名** — 只做文件名优化
4. **仅去重** — 只检测重复文件
5. **撤销操作** — 回退历史操作

### 独立命令

```bash
# 扫描分析（只看报告，不动文件）
python -m filemind scan ~/Downloads

# 完整整理
python -m filemind organize ~/Downloads            # 执行
python -m filemind organize ~/Downloads --dry-run   # 预览
python -m filemind organize ~/Downloads --time-archive  # 启用时间归档

# 检测重复文件
python -m filemind duplicates ~/Downloads

# 撤销操作
python -m filemind undo --list                    # 列出历史操作
python -m filemind undo --session <session_id>    # 撤销指定会话
python -m filemind undo ~/Downloads               # 撤销最近一次

# 配置管理
python -m filemind config --init   # 初始化默认配置
python -m filemind config --show   # 显示当前配置
python -m filemind config --edit   # 编辑配置文件

# MCP 服务器
python -m filemind serve                          # stdio 模式（默认）
python -m filemind serve --transport sse --port 8080  # SSE 模式
```

所有命令支持 `--hidden` 参数扫描隐藏文件。

## 内容识别

超越文件名分析，深入文件内容：

| 文件类型 | 识别方式 | 识别内容 |
|---------|---------|---------|
| PDF | pdfplumber 提取文本（前 3 页） | 发票、合同、简历、论文、财报 |
| 图片 | pytesseract OCR（中英文） | 截图、证件、扫描件 |
| 文本 | 直接读取 | 代码、配置、日志 |

识别结果会反馈到价值评估中，提升分类准确性。

## 三维分析

| 维度 | 等级 | 判断依据 |
|------|------|---------|
| 价值 | 高/中/低 | 文件类型 + 修改时间 + 文件大小 + 内容识别 + 垃圾关键词 |
| 用途 | 工作/学习/个人/临时/未知 | 文件名关键词 + 所在目录名 |
| 风险 | 安全/需谨慎/高风险 | 近期活跃代码 → 高风险；大文件 → 需谨慎；临时文件 → 安全 |

## 重复检测

三种检测模式：

| 模式 | 算法 | 适用场景 |
|------|------|---------|
| 精确匹配 | 大小初筛 + MD5 哈希 | 完全相同的文件 |
| 相似图片 | 感知哈希 (pHash) + Union-Find 聚类 | 不同分辨率/压缩的图片 |
| 视频重复 | 首帧提取 + pHash + 元数据比对 | 不同编码的相同视频 |

## 重命名策略

| 策略 | 行为 |
|------|------|
| `clean`（默认） | 清理 `(1)`、`copy`、`FINAL`、URL 编码、全角字符等垃圾后缀，高价值文件保守处理 |
| `date_prefix` | 所有文件加 `YYYY-MM-DD_` 前缀 |
| `keep` | 仅清理危险字符（全角、URL 编码），尽量不动 |

分类感知：截图自动命名为 `Screenshot_YYYY-MM-DD_HHMMSS`，安装包保留产品名，图片/视频/音乐使用日期回退。

## 配置文件

配置路径：`~/.filemind/config.yaml`

```yaml
thresholds:
  large_file_mb: 100        # 大文件阈值
  old_file_days: 180        # 旧文件天数
  valuable_file_min_kb: 10  # 有价值文件最小体积
  temp_file_max_days: 30    # 临时文件最大保留天数

behavior:
  rename_strategy: clean    # clean / date_prefix / keep
  handle_duplicates: move   # 重复文件处理方式
  auto_confirm: false       # 自动确认（跳过交互）
  create_subfolders: true   # 创建分类子目录
  time_archive: false       # 启用时间归档
  time_archive_format: "%Y/%B"  # 归档目录格式

classification:
  junk_keywords:            # 垃圾关键词
    - copy
    - 副本
    - backup
    - final
  screenshot_patterns: []   # 截图匹配模式
  temp_patterns: []         # 临时文件模式

folder_structure:           # 自定义目录映射
  downloads:                # 下载目录的分类
    Images: "图片"
    Documents: "文档"
    Code: "代码"
  general: {}               # 通用目录的分类

analysis:
  enable_value_assessment: true
  enable_purpose_detection: true
  risk_threshold: medium
```

## MCP Server

内置 MCP (Model Context Protocol) 服务器，可将 FileMind 的能力暴露给 Claude 等 AI Agent：

```bash
# 启动服务器
python -m filemind serve --transport sse --port 8080
```

提供 6 个工具：

| 工具 | 功能 |
|------|------|
| `scan_directory` | 扫描并分析目录 |
| `move_file` | 移动文件（含风险评估和审计日志） |
| `rename_file` | 智能重命名（高风险操作需确认） |
| `analyze_duplicate_files` | 三种模式的重复检测 |
| `generate_summary_report` | 生成完整分析报告 |
| `create_folder` | 创建目录 |

## 项目结构

```
filemind/
├── __init__.py         # 版本声明 (2.1.0)
├── __main__.py         # python -m 入口
├── cli.py              # Click CLI（agent/scan/organize/undo/config/serve）
├── config.py           # YAML 配置管理
├── scanner.py          # 目录扫描与 12 类文件分类
├── analyzer.py         # 三维分析：价值/用途/风险
├── content_analyzer.py # 内容识别：PDF/OCR/文本
├── renamer.py          # 智能重命名引擎
├── organizer.py        # 整理方案生成与执行
├── duplicates.py       # 重复检测：哈希/感知哈希/视频
├── reporter.py         # Rich 终端报告
├── undo.py             # 操作审计与撤销
├── tools.py            # 统一工具层（MCP/CLI/REST 复用）
└── mcp_server.py       # MCP 协议服务器
```

## 数据目录

- `~/.filemind/config.yaml` — 用户配置
- `~/.filemind/undo_logs/` — 操作审计日志（JSON 格式）

## License

MIT
