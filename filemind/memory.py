"""Memory module — learns from user behavior to improve future decisions."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path.home() / ".filemind"
MEMORY_PATH = MEMORY_DIR / "memory.json"

# Junk indicators used to extract keyword signals from filenames
JUNK_INDICATORS = [
    "copy", "副本", "backup", "bak", "old", "temp", "untitled",
    "新建", "未命名", "test", "debug", "final", "v2", "v3", "tmp",
]

# Extension to category mapping for signal extraction
EXT_CATEGORY = {
    ".pdf": "PDF", ".doc": "文档", ".docx": "文档", ".xls": "文档",
    ".xlsx": "文档", ".ppt": "文档", ".pptx": "文档", ".txt": "文档",
    ".csv": "文档", ".md": "文档",
    ".jpg": "图片", ".jpeg": "图片", ".png": "图片", ".gif": "图片",
    ".bmp": "图片", ".svg": "图片", ".webp": "图片", ".heic": "图片",
    ".mp4": "视频", ".avi": "视频", ".mkv": "视频", ".mov": "视频",
    ".wmv": "视频", ".flv": "视频",
    ".mp3": "音乐", ".wav": "音乐", ".flac": "音乐", ".aac": "音乐",
    ".py": "代码", ".js": "代码", ".ts": "代码", ".java": "代码",
    ".c": "代码", ".cpp": "代码", ".go": "代码", ".rs": "代码",
    ".html": "代码", ".css": "代码", ".json": "代码", ".xml": "代码",
    ".zip": "压缩包", ".rar": "压缩包", ".7z": "压缩包", ".tar": "压缩包", ".gz": "压缩包",
    ".dmg": "安装包", ".pkg": "安装包", ".exe": "安装包", ".msi": "安装包",
    ".apk": "安装包",
}


@dataclass
class KeywordSignal:
    keyword: str = ""
    accept: int = 0
    reject: int = 0
    last_seen: str = ""


@dataclass
class CategoryPreference:
    category: str = ""
    folder: str = ""
    accept: int = 0
    reject: int = 0
    last_seen: str = ""


@dataclass
class RenameSignal:
    pattern: str = ""
    accept: int = 0
    reject: int = 0
    last_seen: str = ""


@dataclass
class RiskCalibration:
    risky_accepted: int = 0
    risky_rejected: int = 0
    safe_accepted: int = 0
    safe_rejected: int = 0


@dataclass
class MemoryStore:
    version: int = 1
    junk_keywords: dict = field(default_factory=dict)
    keep_keywords: dict = field(default_factory=dict)
    category_preferences: dict = field(default_factory=dict)
    rename_patterns: dict = field(default_factory=dict)
    risk_calibration: dict = field(default_factory=lambda: asdict(RiskCalibration()))
    purpose_keywords: dict = field(default_factory=dict)
    total_signals: int = 0
    last_updated: str = ""


_instance: Optional[MemoryStore] = None


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def load_memory(path: Path = None) -> MemoryStore:
    path = path or MEMORY_PATH
    if not path.exists():
        return MemoryStore()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mem = MemoryStore(
            version=data.get("version", 1),
            junk_keywords=data.get("junk_keywords", {}),
            keep_keywords=data.get("keep_keywords", {}),
            category_preferences=data.get("category_preferences", {}),
            rename_patterns=data.get("rename_patterns", {}),
            risk_calibration=data.get("risk_calibration", asdict(RiskCalibration())),
            purpose_keywords=data.get("purpose_keywords", {}),
            total_signals=data.get("total_signals", 0),
            last_updated=data.get("last_updated", ""),
        )
        return mem
    except Exception:
        return MemoryStore()


def save_memory(mem: MemoryStore = None, path: Path = None):
    global _instance
    if mem is None:
        mem = _instance or MemoryStore()
    path = path or MEMORY_PATH
    _ensure_dir()
    mem.last_updated = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(mem), f, ensure_ascii=False, indent=2)


def get_memory() -> MemoryStore:
    global _instance
    if _instance is None:
        _instance = load_memory()
    return _instance


def reset_memory():
    global _instance
    _instance = None


# ── Recording functions ──────────────────────────────────────────────

def _now():
    return datetime.now().isoformat()


def _inc_signal(store: dict, key: str, field_name: str, default_obj):
    now = _now()
    if key not in store:
        store[key] = asdict(default_obj) if hasattr(default_obj, '__dataclass_fields__') else default_obj
    store[key][field_name] += 1
    store[key]["last_seen"] = now


def record_junk_signal(keyword: str, accepted: bool):
    mem = get_memory()
    if accepted:
        _inc_signal(mem.junk_keywords, keyword, "accept", KeywordSignal(keyword=keyword))
    else:
        _inc_signal(mem.junk_keywords, keyword, "reject", KeywordSignal(keyword=keyword))
    mem.total_signals += 1
    save_memory()


def record_keep_signal(keyword: str, accepted: bool):
    mem = get_memory()
    if accepted:
        _inc_signal(mem.keep_keywords, keyword, "accept", KeywordSignal(keyword=keyword))
    else:
        _inc_signal(mem.keep_keywords, keyword, "reject", KeywordSignal(keyword=keyword))
    mem.total_signals += 1
    save_memory()


def record_category_preference(category: str, folder: str, accepted: bool):
    mem = get_memory()
    key = f"{category}|{folder}"
    if key not in mem.category_preferences:
        mem.category_preferences[key] = asdict(CategoryPreference(category=category, folder=folder))
    if accepted:
        mem.category_preferences[key]["accept"] += 1
    else:
        mem.category_preferences[key]["reject"] += 1
    mem.category_preferences[key]["last_seen"] = _now()
    mem.total_signals += 1
    save_memory()


def record_rename_signal(pattern: str, accepted: bool):
    mem = get_memory()
    if accepted:
        _inc_signal(mem.rename_patterns, pattern, "accept", RenameSignal(pattern=pattern))
    else:
        _inc_signal(mem.rename_patterns, pattern, "reject", RenameSignal(pattern=pattern))
    mem.total_signals += 1
    save_memory()


def record_risk_decision(risk_level: str, accepted: bool):
    mem = get_memory()
    rc = mem.risk_calibration
    if risk_level in ("risky", "caution"):
        if accepted:
            rc["risky_accepted"] = rc.get("risky_accepted", 0) + 1
        else:
            rc["risky_rejected"] = rc.get("risky_rejected", 0) + 1
    else:
        if accepted:
            rc["safe_accepted"] = rc.get("safe_accepted", 0) + 1
        else:
            rc["safe_rejected"] = rc.get("safe_rejected", 0) + 1
    mem.total_signals += 1
    save_memory()


def record_purpose_keyword(purpose: str, keyword: str):
    mem = get_memory()
    if purpose not in mem.purpose_keywords:
        mem.purpose_keywords[purpose] = []
    if keyword not in mem.purpose_keywords[purpose]:
        mem.purpose_keywords[purpose].append(keyword)
    save_memory()


def _infer_category(source: str) -> str:
    ext = Path(source).suffix.lower()
    return EXT_CATEGORY.get(ext, "")


def _extract_keyword_signals(filename: str, stem: str, accepted: bool):
    for kw in JUNK_INDICATORS:
        if kw in stem:
            if accepted:
                record_junk_signal(kw, True)
            else:
                record_junk_signal(kw, False)
                record_keep_signal(kw, True)


def _normalize_rename_pattern(old_name: str, new_name: str) -> str:
    import re
    pattern = new_name
    pattern = re.sub(r"\d{4}-\d{2}-\d{2}", "{date}", pattern)
    pattern = re.sub(r"\d{8}", "{date}", pattern)
    pattern = re.sub(r"\d{6}", "{time}", pattern)
    pattern = re.sub(r"_\d+$", "_{N}", pattern)
    return Path(pattern).stem


def record_session_feedback(operations: list, accepted: bool):
    """Extract and record signals from a batch of operations."""
    for op in operations:
        if hasattr(op, "status") and op.status != "success":
            continue

        source = getattr(op, "source", "")
        destination = getattr(op, "destination", "")
        operation = getattr(op, "operation", "")

        if not source:
            continue

        source_name = Path(source).name.lower()
        source_stem = Path(source).stem.lower()

        if operation == "move":
            dest_folder = Path(destination).parent.name if destination else ""
            category = _infer_category(source)
            if category and dest_folder:
                record_category_preference(category, dest_folder, accepted)
            _extract_keyword_signals(source_name, source_stem, accepted)

        elif operation == "rename":
            old_name = Path(source).name
            new_name = Path(destination).name if destination else ""
            if new_name:
                pattern = _normalize_rename_pattern(old_name, new_name)
                if pattern:
                    record_rename_signal(pattern, accepted)
            if not accepted and new_name:
                _extract_keyword_signals(
                    new_name.lower(), Path(new_name).stem.lower(), False
                )
            else:
                _extract_keyword_signals(source_name, source_stem, accepted)

        elif operation == "mark_duplicate":
            _extract_keyword_signals(source_name, source_stem, accepted)


# ── Query functions ──────────────────────────────────────────────────

def get_learned_junk_keywords() -> list:
    mem = get_memory()
    result = []
    for kw, data in mem.junk_keywords.items():
        total = data.get("accept", 0) + data.get("reject", 0)
        if total >= 2 and data.get("accept", 0) / total > 0.6:
            result.append(kw)
    return result


def get_learned_keep_keywords() -> list:
    mem = get_memory()
    result = []
    for kw, data in mem.keep_keywords.items():
        total = data.get("accept", 0) + data.get("reject", 0)
        if total >= 2 and data.get("accept", 0) / total > 0.6:
            result.append(kw)
    return result


def get_preferred_folder(category: str, default: str) -> str:
    mem = get_memory()
    best_key = None
    best_ratio = 0.6
    for key, data in mem.category_preferences.items():
        cat = data.get("category", "")
        if cat != category:
            continue
        total = data.get("accept", 0) + data.get("reject", 0)
        if total < 2:
            continue
        ratio = data.get("accept", 0) / total
        if ratio > best_ratio:
            best_ratio = ratio
            best_key = key
    if best_key:
        return mem.category_preferences[best_key]["folder"]
    return default


def get_rename_bias(pattern: str) -> float:
    mem = get_memory()
    data = mem.rename_patterns.get(pattern)
    if not data:
        return 1.0
    total = data.get("accept", 0) + data.get("reject", 0)
    if total < 2:
        return 1.0
    return data.get("accept", 0) / total


def get_risk_adjustment() -> float:
    mem = get_memory()
    rc = mem.risk_calibration
    risky_total = rc.get("risky_accepted", 0) + rc.get("risky_rejected", 0)
    if risky_total < 3:
        return 0.0
    risky_reject_rate = rc.get("risky_rejected", 0) / risky_total
    return (risky_reject_rate - 0.5) * 0.6


def get_extra_purpose_keywords(purpose: str) -> list:
    mem = get_memory()
    return mem.purpose_keywords.get(purpose, [])


# ── Display ──────────────────────────────────────────────────────────

def format_memory_summary(mem: MemoryStore = None) -> str:
    if mem is None:
        mem = get_memory()

    lines = [
        "=== FileMind 学习记忆 ===",
        f"总信号数: {mem.total_signals}",
        f"最后更新: {mem.last_updated or '无'}",
        "",
    ]

    if mem.junk_keywords:
        lines.append("学习到的垃圾关键词:")
        for kw, data in sorted(mem.junk_keywords.items(), key=lambda x: x[1].get("accept", 0), reverse=True):
            total = data.get("accept", 0) + data.get("reject", 0)
            if total >= 2:
                ratio = data.get("accept", 0) / total * 100
                lines.append(f"  {kw:<16} accept: {data['accept']}  reject: {data['reject']}  ({ratio:.0f}%)")
        lines.append("")

    if mem.keep_keywords:
        lines.append("学习到的重要关键词:")
        for kw, data in sorted(mem.keep_keywords.items(), key=lambda x: x[1].get("accept", 0), reverse=True):
            total = data.get("accept", 0) + data.get("reject", 0)
            if total >= 2:
                ratio = data.get("accept", 0) / total * 100
                lines.append(f"  {kw:<16} accept: {data['accept']}  reject: {data['reject']}  ({ratio:.0f}%)")
        lines.append("")

    if mem.category_preferences:
        lines.append("分类偏好:")
        for key, data in sorted(mem.category_preferences.items()):
            total = data.get("accept", 0) + data.get("reject", 0)
            if total >= 2:
                ratio = data.get("accept", 0) / total * 100
                lines.append(f"  {data['category']:<10} -> {data['folder']:<14} accept: {data['accept']}  reject: {data['reject']}  ({ratio:.0f}%)")
        lines.append("")

    if mem.rename_patterns:
        lines.append("重命名模式:")
        for pattern, data in sorted(mem.rename_patterns.items(), key=lambda x: x[1].get("accept", 0), reverse=True):
            total = data.get("accept", 0) + data.get("reject", 0)
            if total >= 2:
                ratio = data.get("accept", 0) / total * 100
                lines.append(f"  {pattern:<30} accept: {data['accept']}  reject: {data['reject']}  ({ratio:.0f}%)")
        lines.append("")

    rc = mem.risk_calibration
    risky_a = rc.get("risky_accepted", 0)
    risky_r = rc.get("risky_rejected", 0)
    safe_a = rc.get("safe_accepted", 0)
    safe_r = rc.get("safe_rejected", 0)
    if risky_a + risky_r > 0 or safe_a + safe_r > 0:
        lines.append("风险校准:")
        if risky_a + risky_r > 0:
            lines.append(f"  高风险操作: {risky_a} 接受, {risky_r} 拒绝")
        if safe_a + safe_r > 0:
            lines.append(f"  安全操作:   {safe_a} 接受, {safe_r} 拒绝")
        adj = get_risk_adjustment()
        if adj > 0.05:
            lines.append(f"  偏好: 谨慎 (+{adj:.2f})")
        elif adj < -0.05:
            lines.append(f"  偏好: 大胆 ({adj:.2f})")
        else:
            lines.append("  偏好: 中性")
        lines.append("")

    if mem.purpose_keywords:
        lines.append("学习到的用途关键词:")
        for purpose, keywords in mem.purpose_keywords.items():
            lines.append(f"  {purpose}: {', '.join(keywords)}")
        lines.append("")

    if not any([mem.junk_keywords, mem.keep_keywords, mem.category_preferences,
                mem.rename_patterns, mem.purpose_keywords]):
        lines.append("暂无学习记录。执行几次整理操作后，系统会自动学习你的偏好。")

    return "\n".join(lines)
