"""结构化报告输出模块 v2 — 数字管家风格"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

console = Console()

PURPOSE_LABELS = {
    "work": "工作文件",
    "study": "学习资料",
    "personal": "个人文件",
    "temp": "临时文件",
    "unknown": "未知",
}

VALUE_LABELS = {
    "high": "高价值",
    "medium": "中价值",
    "low": "低价值",
}

RISK_LABELS = {
    "safe": "安全",
    "caution": "需谨慎",
    "risky": "高风险",
}

RISK_COLORS = {
    "safe": "green",
    "caution": "yellow",
    "risky": "red",
}


def format_size(size_bytes: int) -> str:
    size = size_bytes
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def print_agent_greeting(target_dir):
    console.print()
    console.print(Panel.fit(
        f"[bold]您好！我是 AI 文件助手。[/]\n"
        f"让我来看看 [cyan]{target_dir}[/] 的情况...",
        border_style="cyan",
    ))


def print_scan_report(result):
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]扫描目录:[/] {result.target_dir}",
        title="[bold white] 扫描结果 [/]",
        border_style="cyan",
    ))

    console.print()
    overview = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    overview.add_column("指标", style="bold")
    overview.add_column("值")
    overview.add_row("文件总数", f"[bold]{result.total_count}[/]")
    overview.add_row("大文件 (>100MB)", f"[yellow]{len(result.large_files)}[/]")
    overview.add_row("精确重复组", f"[red]{len(result.duplicate_groups)}[/]")
    if hasattr(result, "similar_images") and result.similar_images:
        overview.add_row("相似图片组", f"[yellow]{len(result.similar_images)}[/]")
    if hasattr(result, "duplicate_videos") and result.duplicate_videos:
        overview.add_row("重复视频组", f"[yellow]{len(result.duplicate_videos)}[/]")
    overview.add_row("可疑垃圾文件", f"[red]{len(result.suspicious_files)}[/]")
    overview.add_row("扫描错误", f"[dim]{len(result.errors)}[/]")
    console.print(overview)

    # 分类统计
    console.print()
    table = Table(title="文件类型统计", box=box.ROUNDED, show_lines=True)
    table.add_column("类别", style="bold")
    table.add_column("数量", justify="right")
    table.add_column("总大小", justify="right")
    table.add_column("占比", justify="right")

    total = result.total_count or 1
    sorted_cats = sorted(result.category_stats.items(), key=lambda x: x[1], reverse=True)
    for cat, count in sorted_cats:
        size = result.category_sizes.get(cat, 0)
        pct = count / total * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        table.add_row(cat, str(count), format_size(size), f"{bar} {pct:.1f}%")
    console.print(table)

    # 大文件
    if result.large_files:
        console.print()
        ltable = Table(title="大文件 (>100MB)", box=box.ROUNDED)
        ltable.add_column("文件名", style="bold")
        ltable.add_column("大小", justify="right")
        ltable.add_column("路径", style="dim")
        for fi in sorted(result.large_files, key=lambda f: f.size, reverse=True)[:10]:
            ltable.add_row(fi.name, fi.size_str, str(fi.path.parent))
        console.print(ltable)

    # 精确重复文件
    if result.duplicate_groups:
        console.print()
        console.print("[bold red]精确重复文件:[/]")
        for gid, group in list(result.duplicate_groups.items())[:5]:
            console.print(f"  组 {gid}:")
            for fi in group:
                console.print(f"    - {fi.name} ({fi.size_str}) [{fi.modified.strftime('%Y-%m-%d')}]")
        if len(result.duplicate_groups) > 5:
            console.print(f"  ... 还有 {len(result.duplicate_groups) - 5} 组")

    # 相似图片
    if hasattr(result, "similar_images") and result.similar_images:
        console.print()
        console.print("[bold yellow]相似图片:[/]")
        for sg in result.similar_images[:5]:
            console.print(f"  组 {sg.group_id} ({len(sg.files)} 张相似):")
            for fi in sg.files:
                console.print(f"    - {fi.name} ({fi.size_str}) [{fi.modified.strftime('%Y-%m-%d')}]")
        if len(result.similar_images) > 5:
            console.print(f"  ... 还有 {len(result.similar_images) - 5} 组")

    # 重复视频
    if hasattr(result, "duplicate_videos") and result.duplicate_videos:
        console.print()
        console.print("[bold yellow]重复视频:[/]")
        for sg in result.duplicate_videos[:5]:
            console.print(f"  组 {sg.group_id} ({len(sg.files)} 个相似):")
            for fi in sg.files:
                console.print(f"    - {fi.name} ({fi.size_str}) [{fi.modified.strftime('%Y-%m-%d')}]")
        if len(result.duplicate_videos) > 5:
            console.print(f"  ... 还有 {len(result.duplicate_videos) - 5} 组")


def print_analysis_insights(result):
    """输出三维分析面板：价值/用途/风险"""
    if not result.analysis:
        return

    analysis = result.analysis

    # 价值评估
    console.print()
    vtable = Table(title="文件价值评估", box=box.SIMPLE)
    vtable.add_column("等级", style="bold")
    vtable.add_column("数量", justify="right")
    vtable.add_column("说明")
    for value, count in sorted(analysis.value_stats.items(), key=lambda x: ["high", "medium", "low"].index(x[0]) if x[0] in ["high", "medium", "low"] else 99):
        desc = {"high": "重要文档、近期代码", "medium": "一般文件", "low": "临时文件、过期安装包"}.get(value, "")
        vtable.add_row(VALUE_LABELS.get(value, value), str(count), desc)
    console.print(vtable)

    # 用途推断
    ptable = Table(title="文件用途推断", box=box.SIMPLE)
    ptable.add_column("用途", style="bold")
    ptable.add_column("数量", justify="right")
    for purpose, count in sorted(analysis.purpose_stats.items(), key=lambda x: x[1], reverse=True):
        ptable.add_row(PURPOSE_LABELS.get(purpose, purpose), str(count))
    console.print(ptable)

    # 风险评估
    rtable = Table(title="操作风险评估", box=box.SIMPLE)
    rtable.add_column("风险等级", style="bold")
    rtable.add_column("数量", justify="right")
    for risk, count in sorted(analysis.risk_stats.items(), key=lambda x: ["safe", "caution", "risky"].index(x[0]) if x[0] in ["safe", "caution", "risky"] else 99):
        color = RISK_COLORS.get(risk, "white")
        rtable.add_row(f"[{color}]{RISK_LABELS.get(risk, risk)}[/]", str(count))
    console.print(rtable)

    # 策略建议
    if analysis.recommendations:
        console.print()
        console.print("[bold]我的建议:[/]")
        for rec in analysis.recommendations:
            console.print(f"  [cyan]▸[/] {rec}")


def print_strategy_explanation(plan):
    """输出策略说明"""
    console.print()
    console.print(Panel.fit(
        f"[bold]整理策略[/]\n\n{plan.strategy_summary}",
        title="[bold white] 分类方案 [/]",
        border_style="yellow",
    ))

    if plan.warnings:
        console.print()
        for w in plan.warnings:
            console.print(f"  [yellow]⚠ {w}[/]")

    # 移动操作
    if plan.actions:
        console.print()
        console.print(f"[bold]文件移动 ({len(plan.actions)} 个操作):[/]")
        by_dest = {}
        for action in plan.actions:
            dest_dir = action.destination.parent.name
            by_dest.setdefault(dest_dir, []).append(action)

        for dest_dir, actions in sorted(by_dest.items()):
            console.print(f"  📁 [cyan]{dest_dir}/[/]")
            for a in actions[:6]:
                risk_badge = ""
                if a.risk == "risky":
                    risk_badge = " [red][高风险][/]"
                elif a.risk == "caution":
                    risk_badge = " [yellow][谨慎][/]"
                console.print(f"    ← {a.source.name}{risk_badge}")
            if len(actions) > 6:
                console.print(f"    ... 还有 {len(actions) - 6} 个文件")

    # 重命名操作
    if plan.rename_actions:
        console.print()
        console.print(f"[bold]智能重命名 ({len(plan.rename_actions)} 个操作):[/]")
        for a in plan.rename_actions[:10]:
            console.print(f"  {a.description}")
        if len(plan.rename_actions) > 10:
            console.print(f"  ... 还有 {len(plan.rename_actions) - 10} 个文件")

    # 重复文件
    if plan.duplicate_actions:
        console.print()
        console.print(f"[bold]重复文件 ({len(plan.duplicate_actions)} 个):[/]")
        console.print("  将移动到 [yellow]Duplicates/[/] 目录，保留最新版本")
        for a in plan.duplicate_actions[:5]:
            console.print(f"  ⚠ {a.source.name} — {a.description}")
        if len(plan.duplicate_actions) > 5:
            console.print(f"  ... 还有 {len(plan.duplicate_actions) - 5} 个重复文件")

    total = len(plan.actions) + len(plan.rename_actions) + len(plan.duplicate_actions)
    console.print()
    console.print(f"[bold]共计 [yellow]{total}[/] 个操作[/]")


def print_execution_logs(logs, session_id=None):
    console.print()
    console.print(Panel.fit(
        "[bold]正在执行整理...[/]",
        title="[bold white] 执行结果 [/]",
        border_style="green",
    ))
    console.print()

    ok_count = 0
    err_count = 0
    for log in logs:
        if log.startswith("[OK]") or log.startswith("[DRY RUN]") or log.startswith("[DUP]"):
            console.print(f"  [green]{log}[/]")
            ok_count += 1
        elif log.startswith("[ERROR]"):
            console.print(f"  [red]{log}[/]")
            err_count += 1
        else:
            console.print(f"  {log}")

    console.print()
    console.print(f"[green]成功: {ok_count}[/]" + (f"  [red]失败: {err_count}[/]" if err_count else ""))

    if session_id:
        console.print()
        console.print(f"[dim]操作已记录。如需撤销，运行:[/]")
        console.print(f"  [cyan]python -m ai_file_assistant undo --session {session_id}[/]")


def print_final_tree(target_dir, result):
    console.print()
    tree = Tree(f"📁 [bold]{target_dir.name}[/]", guide_style="bold blue")

    subdirs = {}
    for fi in result.files:
        if fi.is_duplicate:
            continue
        parent = fi.path.parent
        if parent == target_dir:
            subdirs.setdefault("(根目录)", []).append(fi)
        else:
            rel = parent.relative_to(target_dir)
            subdirs.setdefault(str(rel.parts[0]), []).append(fi)

    for dirname, files in sorted(subdirs.items()):
        branch = tree.add(f"📁 [cyan]{dirname}[/] ({len(files)} 个文件)")
        for fi in files[:5]:
            branch.add(f"  {fi.name}")
        if len(files) > 5:
            branch.add(f"  [dim]... 还有 {len(files) - 5} 个文件[/]")

    console.print()
    console.print(Panel(tree, title="[bold white] 最终目录结构 [/]", border_style="green"))


def print_undo_history(sessions):
    """输出撤销历史"""
    if not sessions:
        console.print("[dim]没有找到操作记录。[/]")
        return

    console.print()
    table = Table(title="操作历史", box=box.ROUNDED)
    table.add_column("会话 ID", style="bold")
    table.add_column("时间")
    table.add_column("目录")
    table.add_column("成功", justify="right")
    table.add_column("失败", justify="right")

    for s in sessions:
        table.add_row(
            s.session_id,
            s.timestamp[:19],
            str(Path(s.target_dir).name),
            str(s.success_count),
            f"[red]{s.failed_count}[/]" if s.failed_count else "0",
        )
    console.print(table)


def print_undo_result(logs):
    """输出撤销结果"""
    console.print()
    ok = sum(1 for l in logs if l.startswith("[OK]") or l.startswith("[DRY RUN]"))
    skip = sum(1 for l in logs if l.startswith("[SKIP]"))
    err = sum(1 for l in logs if l.startswith("[ERROR]"))

    for log in logs:
        if log.startswith("[OK]") or log.startswith("[DRY RUN]"):
            console.print(f"  [green]{log}[/]")
        elif log.startswith("[SKIP]"):
            console.print(f"  [yellow]{log}[/]")
        elif log.startswith("[ERROR]"):
            console.print(f"  [red]{log}[/]")
        else:
            console.print(f"  {log}")

    console.print()
    console.print(f"[green]恢复: {ok}[/]  [yellow]跳过: {skip}[/]" + (f"  [red]失败: {err}[/]" if err else ""))


def print_risk_warning(plan):
    """输出风险提醒"""
    console.print()
    warnings = [
        "移动操作会改变文件位置",
        "重复文件将被移入 Duplicates/ 目录（不会删除）",
        "建议先使用 --dry-run 预览效果",
        "所有操作均可通过 undo 命令撤销",
    ]

    msg = "[bold yellow]⚠ 风险提醒[/]\n\n"
    for w in warnings:
        msg += f"• {w}\n"
    if plan.warnings:
        msg += "\n"
        for w in plan.warnings:
            msg += f"• {w}\n"

    console.print(Panel(msg, border_style="yellow"))
