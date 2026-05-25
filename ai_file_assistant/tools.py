"""统一工具层 — 供 MCP / CLI / REST API 复用"""

import shutil
from pathlib import Path
from datetime import datetime

from .scanner import scan_directory, ScanResult
from .analyzer import analyze_directory
from .organizer import build_organize_plan, execute_plan
from .renamer import suggest_rename_v2
from .undo import create_session, save_session, log_operation, OperationRecord, list_sessions, undo_session
from .config import get_config
from .reporter import format_size


def _serialize_file_info(fi) -> dict:
    """FileInfo → dict（JSON 安全）"""
    return {
        "name": fi.name,
        "path": str(fi.path),
        "extension": fi.extension,
        "size": fi.size,
        "size_str": fi.size_str,
        "category": fi.category,
        "value": getattr(fi, "value", "medium"),
        "purpose": getattr(fi, "purpose", "unknown"),
        "risk": getattr(fi, "risk", "safe"),
        "reasoning": getattr(fi, "analysis_reasoning", ""),
        "is_duplicate": fi.is_duplicate,
        "modified": fi.modified.isoformat(),
        "created": fi.created.isoformat(),
    }


def _serialize_scan_result(result: ScanResult) -> dict:
    """ScanResult → dict"""
    return {
        "target_dir": str(result.target_dir),
        "total_count": result.total_count,
        "category_stats": dict(result.category_stats),
        "category_sizes": {k: format_size(v) for k, v in result.category_sizes.items()},
        "value_stats": dict(result.value_stats),
        "purpose_stats": dict(result.purpose_stats),
        "risk_stats": dict(result.risk_stats),
        "large_files": [_serialize_file_info(f) for f in result.large_files],
        "duplicate_groups": {
            gid: [_serialize_file_info(f) for f in group]
            for gid, group in result.duplicate_groups.items()
        },
        "suspicious_files": [_serialize_file_info(f) for f in result.suspicious_files],
        "files": [_serialize_file_info(f) for f in result.files],
        "errors": result.errors,
        "recommendations": result.analysis.recommendations if result.analysis else [],
    }


def _risk_from_path(path: str) -> str:
    """简单风险评估"""
    p = Path(path)
    name = p.name.lower()

    # 系统目录
    system_dirs = {"/", "/System", "/usr", "/bin", "/sbin", "/etc", "/private"}
    if str(p) in system_dirs or any(str(p).startswith(d + "/") for d in system_dirs):
        return "risky"

    # 隐藏配置
    if name.startswith(".") and p.parent == Path.home():
        return "caution"

    return "safe"


def tool_scan(path: str) -> dict:
    """扫描目录，返回文件列表和分析结果"""
    try:
        config = get_config()
        result = scan_directory(path, config=config)
        return {
            "success": True,
            "data": _serialize_scan_result(result),
            "warnings": [],
            "risk_level": "safe",
            "undo_session_id": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def tool_move(src: str, dst: str, force: bool = False) -> dict:
    """移动文件。高风险操作需 force=True 确认。"""
    src_path = Path(src).expanduser().resolve()
    dst_path = Path(dst).expanduser().resolve()

    if not src_path.exists():
        return {"success": False, "error": f"源文件不存在: {src_path}", "data": None}

    risk = _risk_from_path(src)

    if risk == "risky" and not force:
        return {
            "success": False,
            "error": "高风险操作，需要确认",
            "data": {"source": str(src_path), "destination": str(dst_path)},
            "warnings": [f"移动 {src_path.name} 到 {dst_path} 是高风险操作"],
            "risk_level": "risky",
            "requires_confirmation": True,
        }

    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists():
            stem = dst_path.stem
            suffix = dst_path.suffix
            counter = 1
            while dst_path.exists():
                dst_path = dst_path.parent / f"{stem}_{counter}{suffix}"
                counter += 1

        # 创建 undo 会话并记录
        session = create_session(str(src_path.parent))
        shutil.move(str(src_path), str(dst_path))
        log_operation(session, OperationRecord(
            operation="move",
            source=str(src_path),
            destination=str(dst_path),
            status="success",
        ))
        save_session(session)

        return {
            "success": True,
            "data": {
                "source": str(src_path),
                "destination": str(dst_path),
                "original_destination": str(dst),
            },
            "warnings": [],
            "risk_level": risk,
            "undo_session_id": session.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def tool_rename(path: str, new_name: str, force: bool = False) -> dict:
    """重命名文件。高风险操作需 force=True 确认。"""
    src_path = Path(path).expanduser().resolve()

    if not src_path.exists():
        return {"success": False, "error": f"文件不存在: {src_path}", "data": None}

    dst_path = src_path.parent / new_name
    risk = _risk_from_path(path)

    if risk == "risky" and not force:
        return {
            "success": False,
            "error": "高风险操作，需要确认",
            "data": {"source": str(src_path), "new_name": new_name},
            "warnings": [f"重命名 {src_path.name} 是高风险操作"],
            "risk_level": "risky",
            "requires_confirmation": True,
        }

    try:
        if dst_path.exists():
            stem = dst_path.stem
            suffix = dst_path.suffix
            counter = 1
            while dst_path.exists():
                dst_path = src_path.parent / f"{stem}_{counter}{suffix}"
                counter += 1

        session = create_session(str(src_path.parent))
        shutil.move(str(src_path), str(dst_path))
        log_operation(session, OperationRecord(
            operation="rename",
            source=str(src_path),
            destination=str(dst_path),
            status="success",
        ))
        save_session(session)

        return {
            "success": True,
            "data": {
                "source": str(src_path),
                "new_name": dst_path.name,
                "path": str(dst_path),
            },
            "warnings": [],
            "risk_level": risk,
            "undo_session_id": session.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def tool_analyze_duplicates(path: str) -> dict:
    """检测重复文件"""
    try:
        config = get_config()
        result = scan_directory(path, config=config, skip_analysis=True)

        groups = {}
        for gid, group in result.duplicate_groups.items():
            groups[gid] = {
                "files": [_serialize_file_info(f) for f in group],
                "size": group[0].size,
                "size_str": group[0].size_str,
                "keep": _serialize_file_info(sorted(group, key=lambda f: f.modified, reverse=True)[0]),
                "duplicates": [_serialize_file_info(f) for f in sorted(group, key=lambda f: f.modified, reverse=True)[1:]],
            }

        total_dup_size = sum(
            sum(f.size for f in group[1:])
            for group in result.duplicate_groups.values()
        )

        return {
            "success": True,
            "data": {
                "total_groups": len(groups),
                "total_duplicate_files": sum(len(g["duplicates"]) for g in groups.values()),
                "recoverable_space": format_size(total_dup_size),
                "groups": groups,
            },
            "warnings": [],
            "risk_level": "safe",
            "undo_session_id": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def tool_generate_report(path: str) -> dict:
    """生成完整结构化报告"""
    try:
        config = get_config()
        result = scan_directory(path, config=config)

        report = _serialize_scan_result(result)

        # 添加策略建议
        plan = build_organize_plan(result, config)
        report["strategy"] = {
            "summary": plan.strategy_summary,
            "move_count": len(plan.actions),
            "rename_count": len(plan.rename_actions),
            "duplicate_count": len(plan.duplicate_actions),
            "warnings": plan.warnings,
        }

        # 添加重命名建议
        renames = []
        for action in plan.rename_actions:
            renames.append({
                "source": str(action.source),
                "new_name": action.destination.name,
                "description": action.description,
            })
        report["rename_suggestions"] = renames

        return {
            "success": True,
            "data": report,
            "warnings": plan.warnings,
            "risk_level": "safe",
            "undo_session_id": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


def tool_create_folder(path: str) -> dict:
    """创建目录"""
    try:
        folder_path = Path(path).expanduser().resolve()
        folder_path.mkdir(parents=True, exist_ok=True)
        return {
            "success": True,
            "data": {"path": str(folder_path), "created": True},
            "warnings": [],
            "risk_level": "safe",
            "undo_session_id": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}
