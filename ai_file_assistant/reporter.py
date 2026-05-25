"""结构化报告输出模块"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from rich import box

from .scanner import ScanResult
from .organizer import OrganizePlan


console = Console()


def print_scan_report(result: ScanResult):
    """输出扫描摘要"""

    # ── 标题 ──
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]扫描目录:[/] {result.target_dir}",
        title="[bold white] 扫描结果 [/]",
        border_style="cyan",
    ))

    # ── 总览 ──
    console.print()
    overview = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    overview.add_column("指标", style="bold")
    overview.add_column("值")
    overview.add_row("文件总数", f"[bold]{result.total_count}[/]")
    overview.add_row("大文件 (>100MB)", f"[yellow]{len(result.large_files)}[/]")
    overview.add_row("重复文件组", f"[red]{len(result.duplicate_groups)}[/]")
    overview.add_row("可疑垃圾文件", f"[red]{len(result.suspicious_files)}[/]")
    overview.add_row("扫描错误", f"[dim]{len(result.errors)}[/]")
    console.print(overview)

    # ── 分类统计 ──
    console.print()
    table = Table(
        title="文件类型统计",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("类别", style="bold")
    table.add_column("数量", justify="right")
    table.add_column("总大小", justify="right")
    table.add_column("占比", justify="right")

    total = result.total_count or 1
    sorted_cats = sorted(
        result.category_stats.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    for cat, count in sorted_cats:
        size = result.category_sizes.get(cat, 0)
        pct = count / total * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        size_str = format_size(size)
        table.add_row(cat, str(count), size_str, f"{bar} {pct:.1f}%")

    console.print(table)

    # ── 大文件 ──
    if result.large_files:
        console.print()
        ltable = Table(title="大文件 (>100MB)", box=box.ROUNDED)
        ltable.add_column("文件名", style="bold")
        ltable.add_column("大小", justify="right")
        ltable.add_column("路径", style="dim")
        for fi in sorted(result.large_files, key=lambda f: f.size, reverse=True)[:10]:
            ltable.add_row(fi.name, fi.size_str, str(fi.path.parent))
        console.print(ltable)

    # ── 重复文件 ──
    if result.duplicate_groups:
        console.print()
        console.print("[bold red]重复文件:[/]")
        for gid, group in list(result.duplicate_groups.items())[:5]:
            console.print(f"  组 {gid}:")
            for fi in group:
                console.print(f"    - {fi.name} ({fi.size_str}) [{fi.modified.strftime('%Y-%m-%d')}]")
        if len(result.duplicate_groups) > 5:
            console.print(f"  ... 还有 {len(result.duplicate_groups) - 5} 组")


def print_organize_plan(plan: OrganizePlan):
    """输出整理方案"""
    console.print()
    console.print(Panel.fit(
        "[bold]以下是我建议的整理方案[/]",
        title="[bold white] 分类方案 [/]",
        border_style="yellow",
    ))

    # 移动操作
    if plan.actions:
        console.print()
        console.print(f"[bold]文件移动 ({len(plan.actions)} 个操作):[/]")
        # 按目标目录分组
        by_dest = {}
        for action in plan.actions:
            dest_dir = action.destination.parent.name
            by_dest.setdefault(dest_dir, []).append(action)

        for dest_dir, actions in sorted(by_dest.items()):
            console.print(f"  📁 [cyan]{dest_dir}/[/]")
            for a in actions[:8]:
                console.print(f"    ← {a.source.name}")
            if len(actions) > 8:
                console.print(f"    ... 还有 {len(actions) - 8} 个文件")

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


def print_execution_logs(logs: list):
    """输出执行日志"""
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


def print_final_tree(target_dir, result: ScanResult):
    """输出最终目录结构"""
    console.print()
    tree = Tree(
        f"📁 [bold]{target_dir.name}[/]",
        guide_style="bold blue",
    )

    # 统计子目录
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


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
