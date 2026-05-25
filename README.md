# AI 文件助手

智能文件整理工具，帮助你自动扫描、分类、重命名和整理电脑中的文件。

## 功能

- **目录扫描** — 分析文件名、类型、大小、时间，判断文件用途
- **智能分类** — 12 种文件类型自动识别（图片/视频/文档/代码/安装包等）
- **智能重命名** — 去除乱码、副本、FINAL 等垃圾后缀，自动补充日期，统一格式
- **重复文件检测** — 大小初筛 + MD5 哈希精检，保留最新版本
- **Downloads 专用规则** — 自动识别安装包、临时下载、浏览器重复下载
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

```bash
# 扫描目录（只看报告，不动文件）
python -m ai_file_assistant scan ~/Downloads

# 预览整理方案（dry-run，不执行）
python -m ai_file_assistant organize ~/Downloads --dry-run

# 执行整理（会先询问确认）
python -m ai_file_assistant organize ~/Downloads

# 跳过确认直接执行
python -m ai_file_assistant organize ~/Downloads -y

# 单独检测重复文件
python -m ai_file_assistant duplicates ~/Downloads

# 包含隐藏文件
python -m ai_file_assistant scan ~/Downloads --hidden
```

## 文件分类

| 类别 | 包含类型 |
|------|----------|
| 图片 | jpg, png, gif, webp, svg, heic, psd, raw... |
| 视频 | mp4, avi, mkv, mov, webm, flv... |
| 音乐 | mp3, wav, flac, aac, ogg, m4a... |
| PDF | pdf |
| 文档 | doc, xls, ppt, txt, md, csv, json, pages, keynote... |
| 代码 | py, js, ts, java, go, rs, html, css, sql... |
| 压缩包 | zip, rar, 7z, tar, gz... |
| 安装包 | dmg, pkg, exe, msi, deb, apk... |
| 截图 | 通过文件名模式自动识别 |
| 临时文件 | tmp, bak, swp, crdownload... |

## 整理效果示例

整理前：
```
Downloads/
├── IMG_9383.PNG
├── Final_v2_REAL_FINAL.pdf
├── report (1).xlsx
├── report (2).xlsx
├── setup_installer.dmg
├── temp_file.tmp
└── project_backup.zip
```

整理后：
```
Downloads/
├── Documents/
│   ├── PDF_2026-05-25.pdf
│   ├── report.xlsx
│   └── report_2.xlsx
├── Images/
│   └── Screenshot_2026-05-25.PNG
├── Installers/
│   └── setup_installer.dmg
├── Archives/
│   └── project.zip
└── Temporary/
    └── file.tmp
```

## 项目结构

```
ai_file_assistant/
├── __init__.py       # 包定义
├── __main__.py       # python -m 入口
├── cli.py            # 命令行界面（scan / organize / duplicates）
├── scanner.py        # 目录扫描与文件分类
├── renamer.py        # 智能重命名引擎
├── organizer.py      # 整理方案生成与执行
└── reporter.py       # 结构化报告输出
```

## License

MIT
