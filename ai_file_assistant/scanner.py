"""目录扫描与文件分类模块"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field


# ── 文件类型定义 ──────────────────────────────────────────────

FILE_CATEGORIES = {
    "图片": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
        ".ico", ".tiff", ".tif", ".heic", ".heif", ".raw", ".cr2",
        ".nef", ".arw", ".psd", ".ai", ".eps",
    },
    "视频": {
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".vob",
    },
    "音乐": {
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
        ".opus", ".aiff", ".ape",
    },
    "PDF": {".pdf"},
    "文档": {
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".md", ".rtf", ".odt", ".ods", ".odp",
        ".csv", ".json", ".xml", ".yaml", ".yml", ".toml",
        ".pages", ".numbers", ".key", ".epub",
    },
    "代码": {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
        ".h", ".hpp", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
        ".scala", ".sh", ".bash", ".zsh", ".sql", ".html", ".css",
        ".scss", ".less", ".vue", ".svelte", ".r", ".m", ".mm",
        ".lua", ".pl", ".ex", ".exs", ".hs", ".lua", ".dart",
    },
    "压缩包": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".tgz", ".tar.gz", ".tar.bz2", ".tar.xz", ".zst",
    },
    "安装包": {
        ".dmg", ".pkg", ".app", ".exe", ".msi", ".deb", ".rpm",
        ".apk", ".ipa", ".snap", ".flatpak", ".appimage",
    },
    "截图": set(),  # 通过文件名模式识别
    "临时文件": set(),  # 通过文件名模式识别
}

SCREENSHOT_PATTERNS = [
    "screenshot", "screen shot", "屏幕截图", "截屏",
    "capture", "snip", "snipaste", "cleanshot",
]

TEMP_PATTERNS = [
    ".tmp", ".temp", ".bak", ".swp", ".swo", "~",
    ".crdownload", ".partial", ".download", ".ds_store",
    "thumbs.db", "desktop.ini", ".localized",
]


# ── 数据结构 ──────────────────────────────────────────────────

@dataclass
class FileInfo:
    path: Path
    name: str
    extension: str
    size: int  # bytes
    created: datetime
    modified: datetime
    category: str = "未知文件"
    hash: str = ""
    is_duplicate: bool = False
    duplicate_group: int = -1
    value: str = "medium"
    purpose: str = "unknown"
    risk: str = "safe"
    analysis_reasoning: str = ""

    @property
    def size_str(self) -> str:
        size = self.size
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def parent_dir(self) -> str:
        return str(self.path.parent)


@dataclass
class ScanResult:
    target_dir: Path
    files: list = field(default_factory=list)
    total_count: int = 0
    category_stats: dict = field(default_factory=lambda: defaultdict(int))
    category_sizes: dict = field(default_factory=lambda: defaultdict(int))
    large_files: list = field(default_factory=list)
    duplicate_groups: dict = field(default_factory=dict)
    suspicious_files: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    similar_images: list = field(default_factory=list)
    duplicate_videos: list = field(default_factory=list)
    analysis: object = None
    value_stats: dict = field(default_factory=lambda: defaultdict(int))
    purpose_stats: dict = field(default_factory=lambda: defaultdict(int))
    risk_stats: dict = field(default_factory=lambda: defaultdict(int))


# ── 扫描器 ────────────────────────────────────────────────────

def classify_file(file_info: FileInfo) -> str:
    """根据扩展名和文件名模式判断文件类别"""
    ext = file_info.extension.lower()
    name_lower = file_info.name.lower()

    # 截图检测
    if any(p in name_lower for p in SCREENSHOT_PATTERNS):
        return "截图"

    # 临时文件检测
    if any(p in name_lower for p in TEMP_PATTERNS):
        return "临时文件"
    if ext in TEMP_PATTERNS:
        return "临时文件"

    # 按扩展名分类
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category

    return "未知文件"


def compute_file_hash(filepath: Path, chunk_size: int = 8192) -> str:
    """计算文件 MD5 哈希（用于重复检测）"""
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return ""


def scan_directory(target_dir: str, include_hidden: bool = False, config=None, skip_analysis: bool = False) -> ScanResult:
    """扫描目录，返回完整的扫描结果"""
    from .config import get_config
    from .analyzer import analyze_directory

    if config is None:
        config = get_config()

    target = Path(target_dir).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"目录不存在: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"不是目录: {target}")

    result = ScanResult(target_dir=target)
    size_groups = defaultdict(list)

    large_threshold = config.thresholds.large_file_mb * 1024 * 1024
    junk_keywords = config.classification.junk_keywords

    for root, dirs, files in os.walk(target, followlinks=False):
        root_path = Path(root)

        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]

        for fname in files:
            if not include_hidden and fname.startswith("."):
                continue

            fpath = root_path / fname
            try:
                stat = fpath.stat()
                ext = fpath.suffix
                fi = FileInfo(
                    path=fpath,
                    name=fname,
                    extension=ext,
                    size=stat.st_size,
                    created=datetime.fromtimestamp(stat.st_ctime),
                    modified=datetime.fromtimestamp(stat.st_mtime),
                )
                fi.category = classify_file(fi)

                result.files.append(fi)
                result.total_count += 1
                result.category_stats[fi.category] += 1
                result.category_sizes[fi.category] += fi.size

                if fi.size > large_threshold:
                    result.large_files.append(fi)

                if fi.size > 0:
                    size_groups[fi.size].append(fi)

            except (OSError, PermissionError) as e:
                result.errors.append(f"无法读取: {fpath} ({e})")

    # 重复文件检测
    dup_group_id = 0
    for size, group in size_groups.items():
        if len(group) < 2:
            continue
        hash_groups = defaultdict(list)
        for fi in group:
            if not fi.hash:
                fi.hash = compute_file_hash(fi.path)
            if fi.hash:
                hash_groups[fi.hash].append(fi)
        for h, hash_group in hash_groups.items():
            if len(hash_group) >= 2:
                dup_group_id += 1
                result.duplicate_groups[dup_group_id] = hash_group
                for fi in hash_group:
                    fi.is_duplicate = True
                    fi.duplicate_group = dup_group_id

    # 高级重复检测：相似图片 + 重复视频
    from .duplicates import find_similar_images, find_duplicate_videos
    result.similar_images = find_similar_images(result.files)
    result.duplicate_videos = find_duplicate_videos(result.files)

    # 可疑垃圾文件
    for fi in result.files:
        name_lower = fi.name.lower()
        if any(kw in name_lower for kw in junk_keywords):
            result.suspicious_files.append(fi)
        elif fi.category == "临时文件":
            result.suspicious_files.append(fi)

    result.files.sort(key=lambda f: (f.category, f.name.lower()))

    # 智能分析
    if not skip_analysis:
        result.analysis = analyze_directory(result, config)
        result.value_stats = result.analysis.value_stats
        result.purpose_stats = result.analysis.purpose_stats
        result.risk_stats = result.analysis.risk_stats

    return result
