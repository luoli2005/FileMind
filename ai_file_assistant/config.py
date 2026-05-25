"""用户配置模块 — YAML 配置管理"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


CONFIG_DIR = Path.home() / ".ai_file_assistant"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

_instance: Optional["AppConfig"] = None


@dataclass
class FolderStructureConfig:
    downloads: dict = field(default_factory=lambda: {
        "Documents": ["文档", "PDF"],
        "Images": ["图片", "截图"],
        "Videos": ["视频"],
        "Music": ["音乐"],
        "Installers": ["安装包"],
        "Archives": ["压缩包"],
        "Code": ["代码"],
        "Temporary": ["临时文件"],
        "Others": ["未知文件"],
    })
    general: dict = field(default_factory=lambda: {
        "Documents": ["文档", "PDF"],
        "Photos": ["图片"],
        "Screenshots": ["截图"],
        "Videos": ["视频"],
        "Music": ["音乐"],
        "Software": ["安装包"],
        "Archives": ["压缩包"],
        "Code": ["代码"],
        "Cleanup": ["临时文件"],
        "Others": ["未知文件"],
    })
    custom: Optional[dict] = None


@dataclass
class ClassificationConfig:
    extra_categories: dict = field(default_factory=dict)
    screenshot_patterns: list = field(default_factory=lambda: [
        "screenshot", "screen shot", "屏幕截图", "截屏",
        "capture", "snip", "snipaste", "cleanshot",
    ])
    temp_patterns: list = field(default_factory=lambda: [
        ".tmp", ".temp", ".bak", ".swp", ".swo", "~",
        ".crdownload", ".partial", ".download", ".ds_store",
        "thumbs.db", "desktop.ini", ".localized",
    ])
    junk_keywords: list = field(default_factory=lambda: [
        "copy", "副本", "backup", "bak", "old", "temp",
        "untitled", "新建", "未命名", "test", "debug",
    ])


@dataclass
class ThresholdConfig:
    large_file_mb: int = 100
    old_file_days: int = 180
    valuable_file_min_kb: int = 10
    temp_file_max_days: int = 30


@dataclass
class BehaviorConfig:
    auto_confirm: bool = False
    create_subfolders: bool = True
    handle_duplicates: str = "move"
    rename_strategy: str = "clean"


@dataclass
class AnalysisConfig:
    enable_value_assessment: bool = True
    enable_purpose_detection: bool = True
    risk_threshold: str = "medium"


@dataclass
class AppConfig:
    folder_structure: FolderStructureConfig = field(default_factory=FolderStructureConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)


def _dataclass_to_dict(obj) -> dict:
    """递归将 dataclass 转为 dict"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _dataclass_to_dict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [_dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    return obj


def _dict_to_dataclass(cls, data: dict):
    """递归将 dict 转为 dataclass"""
    if not isinstance(data, dict):
        return data
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    kwargs = {}
    for key, value in data.items():
        if key not in field_types:
            continue
        ft = cls.__dataclass_fields__[key].type
        # 解析类型字符串
        if hasattr(ft, "__dataclass_fields__") and isinstance(value, dict):
            kwargs[key] = _dict_to_dataclass(ft, value)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: Path = None) -> AppConfig:
    """从 YAML 文件加载配置，不存在则返回默认值"""
    global _instance
    config_path = path or CONFIG_PATH

    if not config_path.exists():
        return AppConfig()

    if yaml is None:
        return AppConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return _dict_to_dataclass(AppConfig, data)
    except Exception:
        return AppConfig()


def save_config(config: AppConfig, path: Path = None):
    """将配置保存到 YAML 文件"""
    if yaml is None:
        raise RuntimeError("需要安装 pyyaml: pip install pyyaml")

    config_path = path or CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = _dataclass_to_dict(config)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def init_config(path: Path = None) -> Path:
    """初始化默认配置文件（如已存在则跳过）"""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        save_config(AppConfig(), config_path)
    return config_path


def get_config() -> AppConfig:
    """获取全局配置单例"""
    global _instance
    if _instance is None:
        _instance = load_config()
    return _instance


def reset_config():
    """重置单例（用于测试）"""
    global _instance
    _instance = None
