# AI 文件助手 v2

具有自主决策能力的智能文件管理 Agent。帮助你自动扫描、分析、分类、重命名和整理电脑中的文件。

## 核心能力

- **智能分析** — 评估文件价值（高/中/低）、推断用途（工作/学习/个人/临时）、评估操作风险
- **智能分类** — 12 种文件类型自动识别（图片/视频/文档/代码/安装包等）
- **智能重命名** — 三种策略：清理垃圾后缀 / 日期前缀 / 保留原名
- **重复文件检测** — 大小初筛 + MD5 哈希精检，保留最新版本
- **操作审计** — 每次操作自动记录，支持一键撤销
- **用户配置** — YAML 配置文件，自定义分类规则、目录结构、阈值
- **安全第一** — 不删除任何文件，重复文件移到 `Duplicates/`，危险操作需确认

## 安装

```bash
git clone https://github.com/luoli2005/AI-.git
cd AI-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 使用

### Agent 模式（推荐）

```bash
# 交互式智能整理
python -m ai_file_assistant agent ~/Downloads
```

Agent 模式会：扫描 → 分析价值/用途/风险 → 生成策略 → 交互菜单 → 确认执行 → 记录审计日志

### 独立命令

```bash
# 扫描目录（只看报告，不动文件）
python -m ai_file_assistant scan ~/Downloads

# 预览整理方案（dry-run）
python -m ai_file_assistant organize ~/Downloads --dry-run

# 执行整理
python -m ai_file_assistant organize ~/Downloads

# 检测重复文件
python -m ai_file_assistant duplicates ~/Downloads

# 撤销操作
python -m ai_file_assistant undo --list           # 列出历史操作
python -m ai_file_assistant undo --session abc123  # 撤销指定会话
python -m ai_file_assistant undo ~/Downloads        # 撤销最近一次

# 配置管理
python -m ai_file_assistant config --init  # 初始化默认配置
python -m ai_file_assistant config --show  # 显示当前配置
python -m ai_file_assistant config --edit  # 编辑配置文件
```

## 智能分析

v2 新增三维分析能力：

| 维度 | 等级 | 说明 |
|------|------|------|
| 价值 | 高/中/低 | 重要文档、近期代码 → 高；临时文件 → 低 |
| 用途 | 工作/学习/个人/临时/未知 | 根据文件名关键词推断 |
| 风险 | 安全/需谨慎/高风险 | 近期活跃代码 → 高风险 |

## 重命名策略

| 策略 | 行为 |
|------|------|
| `clean`（默认） | 清理垃圾后缀，高价值文件保守处理 |
| `date_prefix` | 所有文件加 `YYYY-MM-DD_` 前缀 |
| `keep` | 仅清理危险字符，尽量不动 |

## 配置文件

配置路径：`~/.ai_file_assistant/config.yaml`

```yaml
thresholds:
  large_file_mb: 100
  old_file_days: 180

behavior:
  rename_strategy: clean
  handle_duplicates: move

classification:
  junk_keywords:
    - copy
    - 副本
    - backup
    - final
```

## 项目结构

```
ai_file_assistant/
├── __init__.py       # v2.0.0
├── __main__.py       # python -m 入口
├── cli.py            # 命令行（agent / scan / organize / undo / config）
├── config.py         # YAML 配置管理
├── analyzer.py       # 文件价值/用途/风险分析
├── undo.py           # 操作审计与撤销
├── scanner.py        # 目录扫描与文件分类
├── renamer.py        # 智能重命名引擎
├── organizer.py      # 整理方案生成与执行
└── reporter.py       # 数字管家风格报告输出
```

## 数据目录

- `~/.ai_file_assistant/config.yaml` — 用户配置
- `~/.ai_file_assistant/undo_logs/` — 操作审计日志（JSON）

## License

MIT
