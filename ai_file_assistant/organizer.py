"""文件整理执行模块 v2"""

import shutil
from pathlib import Path
from dataclasses import dataclass, field
from .renamer import build_rename_plan


@dataclass
class OrganizeAction:
    action_type: str
    source: Path
    destination: Path = None
    description: str = ""
    risk: str = "safe"
    reasoning: str = ""


@dataclass
class OrganizePlan:
    actions: list = field(default_factory=list)
    rename_actions: list = field(default_factory=list)
    duplicate_actions: list = field(default_factory=list)
    target_dir: Path = None
    warnings: list = field(default_factory=list)
    strategy_summary: str = ""


def detect_folder_type(target_dir: Path) -> str:
    name = target_dir.name.lower()
    if name in ("downloads", "download", "下载"):
        return "downloads"
    if name in ("desktop", "桌面"):
        return "desktop"
    return "general"


def _get_structure(folder_type: str, config=None) -> dict:
    """获取目录结构映射（优先用配置）"""
    if config and hasattr(config, "folder_structure"):
        if config.folder_structure.custom:
            return config.folder_structure.custom
        if folder_type == "downloads":
            return config.folder_structure.downloads
        return config.folder_structure.general

    if folder_type == "downloads":
        return {
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
    return {
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
    }


def build_organize_plan(scan_result, config=None) -> OrganizePlan:
    """根据扫描结果生成整理方案"""
    from .config import get_config
    if config is None:
        config = get_config()

    target = scan_result.target_dir
    folder_type = detect_folder_type(target)
    structure = _get_structure(folder_type, config)

    plan = OrganizePlan(target_dir=target)

    category_to_dir = {}
    for dirname, categories in structure.items():
        for cat in categories:
            category_to_dir[cat] = dirname

    # 时间归档配置
    time_archive = config.behavior.time_archive if config else False
    time_format = config.behavior.time_archive_format if config else "%Y/%B"
    time_categories = set(config.behavior.time_archive_categories if config else [
        "文档", "PDF", "图片", "截图", "视频", "音乐",
    ])

    def _get_dest_dir(fi) -> Path:
        """计算目标目录（含时间归档）"""
        dest_dir_name = category_to_dir.get(fi.category, "Others")
        dest_dir = target / dest_dir_name
        # 时间归档：为指定类别添加 year/month 子目录
        if time_archive and fi.category in time_categories:
            time_path = fi.modified.strftime(time_format)
            dest_dir = dest_dir / time_path
        return dest_dir

    # 1. 移动方案（带风险评估）
    for fi in scan_result.files:
        if fi.is_duplicate:
            continue

        dest_dir = _get_dest_dir(fi)

        if fi.path.parent != dest_dir:
            risk = getattr(fi, "risk", "safe")
            reasoning = getattr(fi, "analysis_reasoning", "")

            # 近期活跃代码文件提升风险
            if fi.category == "代码" and (fi.modified - fi.created).days < 7:
                risk = "risky"
                reasoning = "最近修改的代码文件"

            # 显示相对路径
            rel_path = dest_dir.relative_to(target)
            action = OrganizeAction(
                action_type="move",
                source=fi.path,
                destination=dest_dir / fi.name,
                description=f"{fi.name} → {rel_path}/",
                risk=risk,
                reasoning=reasoning,
            )
            plan.actions.append(action)

    # 2. 重命名方案
    rename_plan = build_rename_plan(scan_result.files, config)
    for fi, old_name, new_name in rename_plan:
        if fi.is_duplicate:
            continue
        dest_dir = _get_dest_dir(fi)
        action = OrganizeAction(
            action_type="rename",
            source=fi.path,
            destination=dest_dir / new_name,
            description=f"{old_name} → {new_name}",
        )
        plan.rename_actions.append(action)

    # 3. 重复文件标记
    for group_id, group in scan_result.duplicate_groups.items():
        group.sort(key=lambda f: f.modified, reverse=True)
        keep = group[0]
        for dup in group[1:]:
            action = OrganizeAction(
                action_type="mark_duplicate",
                source=dup.path,
                destination=target / "Duplicates" / dup.name,
                description=f"与 {keep.name} 重复 (保留最新版本)",
                risk="safe",
            )
            plan.duplicate_actions.append(action)

    # 4. 生成策略摘要
    plan.strategy_summary = _build_strategy_summary(scan_result, plan, target)
    plan.warnings = _build_warnings(plan)

    return plan


def _build_strategy_summary(scan_result, plan, target) -> str:
    """生成人类可读的策略摘要"""
    parts = []
    parts.append(f"扫描到 {scan_result.total_count} 个文件")

    move_count = len(plan.actions)
    rename_count = len(plan.rename_actions)
    dup_count = len(plan.duplicate_actions)

    if move_count > 0:
        dest_dirs = set()
        for a in plan.actions:
            dest_dirs.add(a.destination.parent.name)
        parts.append(f"建议将 {move_count} 个文件整理到 {len(dest_dirs)} 个子目录")

    if rename_count > 0:
        parts.append(f"重命名 {rename_count} 个文件名")

    if dup_count > 0:
        parts.append(f"标记 {dup_count} 个重复文件")

    # 估算重复文件大小
    dup_size = 0
    for group in scan_result.duplicate_groups.values():
        for fi in group[1:]:
            dup_size += fi.size
    if dup_size > 0:
        from .reporter import format_size
        parts.append(f"预计释放 {format_size(dup_size)} 重复空间")

    return "。".join(parts) + "。"


def _build_warnings(plan: OrganizePlan) -> list:
    """从操作列表中提取风险警告"""
    warnings = []
    risky_actions = [a for a in plan.actions if a.risk == "risky"]
    caution_actions = [a for a in plan.actions if a.risk == "caution"]

    if risky_actions:
        names = [a.source.name for a in risky_actions[:3]]
        warnings.append(f"有 {len(risky_actions)} 个高风险操作（如 {', '.join(names)}）")

    if caution_actions:
        warnings.append(f"有 {len(caution_actions)} 个需要谨慎的操作")

    return warnings


def execute_plan(plan: OrganizePlan, dry_run: bool = False, undo_session=None) -> list:
    """执行整理方案，返回操作日志"""
    from .undo import OperationRecord, log_operation

    logs = []
    final_moves = {}

    for action in plan.actions:
        if action.action_type == "move":
            final_moves[action.source] = action.destination

    for action in plan.rename_actions:
        if action.source in final_moves:
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
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = dest.parent / f"{stem}_{counter}{suffix}"
                    counter += 1
            shutil.move(str(source), str(dest))
            logs.append(f"[OK] {source.name} → {dest.parent.name}/{dest.name}")

            if undo_session:
                log_operation(undo_session, OperationRecord(
                    operation="move",
                    source=str(source),
                    destination=str(dest),
                    status="success",
                ))
        except Exception as e:
            logs.append(f"[ERROR] {source.name}: {e}")
            if undo_session:
                log_operation(undo_session, OperationRecord(
                    operation="move",
                    source=str(source),
                    destination=str(dest),
                    status="failed",
                    error=str(e),
                ))

    # 重复文件
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

            if undo_session:
                log_operation(undo_session, OperationRecord(
                    operation="mark_duplicate",
                    source=str(action.source),
                    destination=str(dest),
                    status="success",
                ))
        except Exception as e:
            logs.append(f"[ERROR] 重复文件 {action.source.name}: {e}")

    return logs
