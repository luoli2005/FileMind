"""文件整理执行模块"""

import shutil
from pathlib import Path
from dataclasses import dataclass, field
from .scanner import ScanResult, FileInfo
from .renamer import build_rename_plan


# ── 整理方案 ──────────────────────────────────────────────────

DOWNLOADS_STRUCTURE = {
    "Documents": ["文档", "PDF"],
    "Images": ["图片", "截图"],
    "Videos": ["视频"],
    "Music": ["音乐"],
    "Installers": ["安装包"],
    "Archives": ["压缩包"],
    "Code": ["代码"],
    "Temporary": ["临时文件"],
    "Others": ["未知文件"],
}

GENERAL_STRUCTURE = {
    "Documents": ["文档", "PDF"],
    "Images": ["图片", "截图"],
    "Videos": ["视频"],
    "Music": ["音乐"],
    "Installers": ["安装包"],
    "Archives": ["压缩包"],
    "Code": ["代码"],
    "Temporary": ["临时文件"],
    "Others": ["未知文件"],
}


@dataclass
class OrganizeAction:
    """单个整理操作"""
    action_type: str  # "move" | "rename" | "mark_duplicate"
    source: Path
    destination: Path = None
    description: str = ""


@dataclass
class OrganizePlan:
    """整理方案"""
    actions: list = field(default_factory=list)
    rename_actions: list = field(default_factory=list)
    duplicate_actions: list = field(default_factory=list)
    target_dir: Path = None


def detect_folder_type(target_dir: Path) -> str:
    """检测目标目录类型"""
    name = target_dir.name.lower()
    if name in ("downloads", "download", "下载"):
        return "downloads"
    if name in ("desktop", "桌面"):
        return "desktop"
    return "general"


def build_organize_plan(scan_result: ScanResult) -> OrganizePlan:
    """根据扫描结果生成整理方案"""
    target = scan_result.target_dir
    folder_type = detect_folder_type(target)

    if folder_type == "downloads":
        structure = DOWNLOADS_STRUCTURE
    else:
        structure = GENERAL_STRUCTURE

    plan = OrganizePlan(target_dir=target)

    # 类别 → 子目录映射
    category_to_dir = {}
    for dirname, categories in structure.items():
        for cat in categories:
            category_to_dir[cat] = dirname

    # 1. 移动方案
    for fi in scan_result.files:
        # 跳过重复文件（稍后单独处理）
        if fi.is_duplicate:
            continue

        dest_dir_name = category_to_dir.get(fi.category, "Others")
        dest_dir = target / dest_dir_name
        dest_path = dest_dir / fi.name

        # 只有文件不在目标子目录下才需要移动
        if fi.path.parent != dest_dir:
            action = OrganizeAction(
                action_type="move",
                source=fi.path,
                destination=dest_path,
                description=f"{fi.name} → {dest_dir_name}/",
            )
            plan.actions.append(action)

    # 2. 重命名方案
    rename_plan = build_rename_plan(scan_result.files)
    for fi, old_name, new_name in rename_plan:
        # 确定重命名后的最终路径
        if fi.is_duplicate:
            continue
        dest_dir_name = category_to_dir.get(fi.category, "Others")
        dest_dir = target / dest_dir_name
        action = OrganizeAction(
            action_type="rename",
            source=fi.path,
            destination=dest_dir / new_name,
            description=f"{old_name} → {new_name}",
        )
        plan.rename_actions.append(action)

    # 3. 重复文件标记
    for group_id, group in scan_result.duplicate_groups.items():
        # 按修改时间排序，保留最新
        group.sort(key=lambda f: f.modified, reverse=True)
        keep = group[0]
        for dup in group[1:]:
            action = OrganizeAction(
                action_type="mark_duplicate",
                source=dup.path,
                description=f"与 {keep.name} 重复 (保留最新版本)",
            )
            plan.duplicate_actions.append(action)

    return plan


def execute_plan(plan: OrganizePlan, dry_run: bool = False) -> list:
    """执行整理方案，返回操作日志"""
    logs = []

    # 合并移动和重命名：先确定最终路径，一次移动到位
    # 建立 source → 最终目标 映射
    final_moves = {}

    for action in plan.actions:
        if action.action_type == "move":
            final_moves[action.source] = action.destination

    for action in plan.rename_actions:
        if action.source in final_moves:
            # 已经要移动，更新目标文件名
            dest = final_moves[action.source]
            final_moves[action.source] = dest.parent / action.destination.name
        else:
            final_moves[action.source] = action.destination

    # 执行移动 / 重命名
    for source, dest in final_moves.items():
        if dry_run:
            logs.append(f"[DRY RUN] {source.name} → {dest.parent.name}/{dest.name}")
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            # 处理目标文件已存在的情况
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = dest.parent / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(source), str(dest))
            logs.append(f"[OK] {source.name} → {dest.parent.name}/{dest.name}")
        except Exception as e:
            logs.append(f"[ERROR] {source.name}: {e}")

    # 重复文件：移动到 Duplicates 目录
    for action in plan.duplicate_actions:
        if dry_run:
            logs.append(f"[DRY RUN] 标记重复: {action.source.name}")
            continue

        try:
            dup_dir = plan.target_dir / "Duplicates"
            dup_dir.mkdir(parents=True, exist_ok=True)
            dest = dup_dir / action.source.name
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = dup_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(action.source), str(dest))
            logs.append(f"[DUP] {action.source.name} → Duplicates/")
        except Exception as e:
            logs.append(f"[ERROR] 重复文件 {action.source.name}: {e}")

    return logs
