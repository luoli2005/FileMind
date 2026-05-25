"""操作审计与撤销模块"""

import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

UNDO_DIR = Path.home() / ".filemind" / "undo_logs"


@dataclass
class OperationRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    operation: str = ""
    source: str = ""
    destination: str = ""
    status: str = "success"
    error: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class UndoSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    target_dir: str = ""
    operations: list = field(default_factory=list)
    config_snapshot: dict = field(default_factory=dict)

    @property
    def success_count(self) -> int:
        return sum(1 for op in self.operations if op.status == "success")

    @property
    def failed_count(self) -> int:
        return sum(1 for op in self.operations if op.status == "failed")


def _ensure_undo_dir():
    UNDO_DIR.mkdir(parents=True, exist_ok=True)


def create_session(target_dir: str, config: dict = None) -> UndoSession:
    """创建新的撤销会话"""
    _ensure_undo_dir()
    session = UndoSession(
        target_dir=target_dir,
        config_snapshot=config or {},
    )
    return session


def log_operation(session: UndoSession, op: OperationRecord):
    """记录一条操作到会话"""
    session.operations.append(op)


def save_session(session: UndoSession):
    """将会话持久化到磁盘"""
    _ensure_undo_dir()
    filepath = UNDO_DIR / f"{session.session_id}.json"
    data = {
        "session_id": session.session_id,
        "timestamp": session.timestamp,
        "target_dir": session.target_dir,
        "config_snapshot": session.config_snapshot,
        "operations": [asdict(op) for op in session.operations],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_sessions(target_dir: str = None) -> list:
    """列出所有撤销会话，可按目录过滤"""
    _ensure_undo_dir()
    sessions = []
    for filepath in sorted(UNDO_DIR.glob("*.json"), reverse=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if target_dir and data.get("target_dir") != target_dir:
                continue
            ops = [OperationRecord(**op) for op in data.get("operations", [])]
            session = UndoSession(
                session_id=data["session_id"],
                timestamp=data["timestamp"],
                target_dir=data["target_dir"],
                operations=ops,
                config_snapshot=data.get("config_snapshot", {}),
            )
            sessions.append(session)
        except Exception:
            continue
    return sessions


def get_session(session_id: str) -> Optional[UndoSession]:
    """加载指定会话"""
    filepath = UNDO_DIR / f"{session_id}.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        ops = [OperationRecord(**op) for op in data.get("operations", [])]
        return UndoSession(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            target_dir=data["target_dir"],
            operations=ops,
            config_snapshot=data.get("config_snapshot", {}),
        )
    except Exception:
        return None


def undo_session(session_id: str, dry_run: bool = False) -> list:
    """回滚指定会话的所有操作（逆序）"""
    session = get_session(session_id)
    if not session:
        return [f"[ERROR] 未找到会话: {session_id}"]

    logs = []
    # 逆序回滚
    for op in reversed(session.operations):
        if op.status != "success":
            continue

        if op.operation in ("move", "rename"):
            source = Path(op.source)
            dest = Path(op.destination)

            if dry_run:
                logs.append(f"[DRY RUN] {dest.name} → {source.parent.name}/{source.name}")
                continue

            if not dest.exists():
                logs.append(f"[SKIP] 文件已不存在: {dest}")
                continue

            try:
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(source))
                logs.append(f"[OK] {dest.name} → {source.parent.name}/{source.name}")
            except Exception as e:
                logs.append(f"[ERROR] {dest.name}: {e}")

        elif op.operation == "mark_duplicate":
            dest = Path(op.destination) if op.destination else None
            source = Path(op.source)

            if dry_run:
                logs.append(f"[DRY RUN] 恢复重复文件: {source.name}")
                continue

            if dest and dest.exists():
                try:
                    source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest), str(source))
                    logs.append(f"[OK] 恢复: {source.name}")
                except Exception as e:
                    logs.append(f"[ERROR] {source.name}: {e}")
            else:
                logs.append(f"[SKIP] 文件已不存在: {dest or source}")

    return logs


def undo_last(target_dir: str, dry_run: bool = False) -> list:
    """撤销指定目录的最近一次操作"""
    sessions = list_sessions(target_dir)
    if not sessions:
        return [f"[INFO] 没有找到 {target_dir} 的操作记录"]
    return undo_session(sessions[0].session_id, dry_run)
