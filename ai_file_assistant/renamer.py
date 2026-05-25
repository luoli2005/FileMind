"""智能重命名模块"""

import re
from pathlib import Path
from datetime import datetime


# ── 乱码 / 无意义字符清理 ─────────────────────────────────────

# 常见的下载站 / 浏览器附加后缀
JUNK_SUFFIXES = [
    r"\(\d+\)",           # (1), (2) ...
    r"[-_]?(copy|副本)",  # copy / 副本
    r"[-_]?final",        # final
    r"[-_]?v\d+",         # v2, v3 ...
    r"[-_]?real",         # real
    r"[-_]?new",          # new
    r"[-_]?old",          # old
    r"[-_]?backup",       # backup
    r"[-_]?bak",          # bak
    r"[-_]?tmp",          # tmp
    r"[-_]?temp",         # temp
    r"\s+",               # 多余空格
]

# URL 编码残留
URL_ENCODED = re.compile(r"%[0-9A-Fa-f]{2}")

# 连续特殊字符
MULTI_SPECIAL = re.compile(r"[-_\s]{2,}")

# 中文括号 / 全角字符
FULLWIDTH = {
    "（": "(", "）": ")", "【": "[", "】": "]",
    "：": "-", "；": "-", "，": ",", "。": ".",
    "？": "?", "！": "!", "、": ",",
}

# 截图类文件名模式
SCREENSHOT_RE = re.compile(
    r"^(?:IMG|DSC|DSCN|DCIM|Screenshot|屏幕截图|截屏|Capture)[-_ ]?\d{0,14}",
    re.IGNORECASE,
)


def clean_name(name: str) -> str:
    """清理文件名中的乱码和无意义字符"""
    # 全角 → 半角
    for old, new in FULLWIDTH.items():
        name = name.replace(old, new)

    # URL 编码残留
    name = URL_ENCODED.sub("", name)

    # 去除常见垃圾后缀（逐个 strip）
    for pattern in JUNK_SUFFIXES:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # 连续特殊字符合并为单个 _
    name = MULTI_SPECIAL.sub("_", name)

    # 去除首尾特殊字符
    name = name.strip("-_ .")

    return name


def suggest_rename(file_info: FileInfo) -> str:
    """为文件生成建议名称"""
    name = file_info.name
    ext = file_info.extension
    stem = Path(name).stem
    date_str = file_info.modified.strftime("%Y-%m-%d")

    category = file_info.category

    # ── 截图 ──
    if category == "截图" or SCREENSHOT_RE.match(name):
        return f"Screenshot_{date_str}{ext}"

    # ── 安装包 ──
    if category == "安装包":
        cleaned = clean_name(stem)
        # 保留产品名，去掉版本号后面的乱码
        return f"{cleaned}{ext}" if cleaned else f"Installer_{date_str}{ext}"

    # ── 压缩包 ──
    if category == "压缩包":
        cleaned = clean_name(stem)
        return f"{cleaned}{ext}" if cleaned else f"Archive_{date_str}{ext}"

    # ── 图片 ──
    if category == "图片":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 3:
            return f"{cleaned}{ext}"
        return f"Image_{date_str}{ext}"

    # ── 视频 ──
    if category == "视频":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 3:
            return f"{cleaned}{ext}"
        return f"Video_{date_str}{ext}"

    # ── 音乐 ──
    if category == "音乐":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 3:
            return f"{cleaned}{ext}"
        return f"Audio_{date_str}{ext}"

    # ── 文档 / PDF / 代码 ──
    if category in ("文档", "PDF", "代码"):
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 2:
            return f"{cleaned}{ext}"
        return f"{category}_{date_str}{ext}"

    # ── 通用 ──
    cleaned = clean_name(stem)
    if cleaned and cleaned != stem and len(cleaned) > 2:
        return f"{cleaned}{ext}"

    return ""  # 不需要重命名


def build_rename_plan(files: list, config=None) -> list:
    """为所有文件生成重命名计划，返回 [(FileInfo, old_name, new_name)]"""
    plan = []
    seen_names = {}

    for fi in files:
        new_name = suggest_rename_v2(fi, config)
        if not new_name or new_name == fi.name:
            continue

        dir_key = (fi.parent_dir, new_name)
        if dir_key in seen_names:
            seen_names[dir_key] += 1
            stem = Path(new_name).stem
            ext = Path(new_name).suffix
            new_name = f"{stem}_{seen_names[dir_key]}{ext}"
        else:
            seen_names[dir_key] = 1

        plan.append((fi, fi.name, new_name))

    return plan


def suggest_rename_v2(fi, config=None) -> str:
    """v2 智能重命名：根据文件价值/用途/策略生成名称"""
    strategy = "clean"
    if config and hasattr(config, "behavior"):
        strategy = config.behavior.rename_strategy

    if strategy == "keep":
        return _keep_strategy(fi)
    elif strategy == "date_prefix":
        return _date_prefix_strategy(fi)
    else:
        return _clean_strategy(fi)


def _clean_strategy(fi) -> str:
    """默认策略：清理垃圾后缀，保留有意义的名称"""
    name = fi.name
    ext = fi.extension
    stem = Path(name).stem
    date_str = fi.modified.strftime("%Y-%m-%d")
    category = fi.category

    # 高价值文件：保守清理，尽量保留原名
    if hasattr(fi, "value") and fi.value == "high":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 2:
            return f"{cleaned}{ext}"
        return ""

    # 截图：精确到秒
    if category == "截图":
        time_str = fi.modified.strftime("%Y-%m-%d_%H%M%S")
        return f"Screenshot_{time_str}{ext}"

    # 安装包
    if category == "安装包":
        cleaned = clean_name(stem)
        return f"{cleaned}{ext}" if cleaned else f"Installer_{date_str}{ext}"

    # 压缩包
    if category == "压缩包":
        cleaned = clean_name(stem)
        return f"{cleaned}{ext}" if cleaned else f"Archive_{date_str}{ext}"

    # 图片
    if category == "图片":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 3:
            return f"{cleaned}{ext}"
        return f"Image_{date_str}{ext}"

    # 视频
    if category == "视频":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 3:
            return f"{cleaned}{ext}"
        return f"Video_{date_str}{ext}"

    # 音乐
    if category == "音乐":
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 3:
            return f"{cleaned}{ext}"
        return f"Audio_{date_str}{ext}"

    # 文档/PDF/代码
    if category in ("文档", "PDF", "代码"):
        cleaned = clean_name(stem)
        if cleaned and len(cleaned) > 2:
            return f"{cleaned}{ext}"
        return f"{category}_{date_str}{ext}"

    # 通用
    cleaned = clean_name(stem)
    if cleaned and cleaned != stem and len(cleaned) > 2:
        return f"{cleaned}{ext}"

    return ""


def _date_prefix_strategy(fi) -> str:
    """日期前缀策略：所有文件加日期前缀"""
    ext = fi.extension
    stem = Path(fi.name).stem
    date_str = fi.modified.strftime("%Y-%m-%d")
    cleaned = clean_name(stem)

    if not cleaned or len(cleaned) < 2:
        cleaned = fi.category

    return f"{date_str}_{cleaned}{ext}"


def _keep_strategy(fi) -> str:
    """保留策略：仅清理危险字符，尽量不动"""
    name = fi.name
    # 只清理全角字符和 URL 编码
    for old, new in FULLWIDTH.items():
        name = name.replace(old, new)
    name = URL_ENCODED.sub("", name)

    if name == fi.name:
        return ""
    return name
