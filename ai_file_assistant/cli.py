"""AI 文件助手 - 命令行入口"""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from .scanner import scan_directory
from .organizer import build_organize_plan, execute_plan
from .reporter import (
    print_scan_report,
    print_organize_plan,
    print_execution_logs,
    print_final_tree,
)

console = Console()


BANNER = """
╔══════════════════════════════════════════╗
║         AI 文件助手 v1.0.0              ║
║     智能文件整理 · 安全可靠             ║
╚══════════════════════════════════════════╝
"""


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="1.0.0", prog_name="AI 文件助手")
def cli(ctx):
    """AI 文件助手 — 智能文件整理工具

    帮助你自动扫描、分类、重命名和整理文件。

    \b
    使用示例:
      python -m ai_file_assistant scan ~/Downloads
      python -m ai_file_assistant organize ~/Downloads
      python -m ai_file_assistant organize ~/Desktop --dry-run
    """
    if ctx.invoked_subcommand is None:
        console.print(Panel(BANNER, border_style="cyan"))
        console.print(ctx.get_help())


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--hidden", is_flag=True, help="包含隐藏文件")
def scan(directory, hidden):
    """扫描目录，输出文件分析报告"""
    target = Path(directory).expanduser().resolve()
    console.print(Panel.fit(
        f"[bold]正在扫描:[/] {target}",
        border_style="cyan",
    ))

    with console.status("[bold green]扫描中..."):
        result = scan_directory(str(target), include_hidden=hidden)

    print_scan_report(result)


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--dry-run", is_flag=True, help="仅预览，不执行操作")
@click.option("--hidden", is_flag=True, help="包含隐藏文件")
@click.option("--yes", "-y", is_flag=True, help="跳过确认，直接执行")
def organize(directory, dry_run, hidden, yes):
    """扫描、规划并整理目录（完整流程）"""
    target = Path(directory).expanduser().resolve()

    # ── 步骤1: 扫描 ──
    console.print(Panel.fit(
        f"[bold]正在扫描:[/] {target}",
        title="[bold white] 步骤 1/6 · 扫描目录 [/]",
        border_style="cyan",
    ))
    with console.status("[bold green]扫描中..."):
        result = scan_directory(str(target), include_hidden=hidden)

    # ── 步骤2: 扫描摘要 ──
    print_scan_report(result)

    if result.total_count == 0:
        console.print("[yellow]目录为空，无需整理。[/]")
        return

    # ── 步骤3: 整理方案 ──
    console.print()
    console.print(Panel.fit(
        "[bold]正在生成整理方案...[/]",
        title="[bold white] 步骤 3/6 · 分类方案 [/]",
        border_style="yellow",
    ))
    plan = build_organize_plan(result)
    print_organize_plan(plan)

    total_ops = len(plan.actions) + len(plan.rename_actions) + len(plan.duplicate_actions)
    if total_ops == 0:
        console.print("[green]目录已经很整洁，无需整理！[/]")
        return

    # ── 步骤4: 风险提醒 & 确认 ──
    console.print()
    console.print(Panel(
        "[bold yellow]⚠ 风险提醒[/]\n\n"
        "• 移动操作会改变文件位置\n"
        "• 重复文件将被移入 Duplicates/ 目录（不会删除）\n"
        "• 建议先使用 --dry-run 预览效果\n"
        "• 所有操作均可手动撤销（从子目录移回原位）",
        border_style="yellow",
    ))

    if dry_run:
        console.print("\n[bold cyan]🔍 预览模式 (--dry-run)，不会执行任何操作[/]\n")
        logs = execute_plan(plan, dry_run=True)
        print_execution_logs(logs)
        return

    # ── 步骤5: 等待确认 ──
    if not yes:
        console.print()
        if not Confirm.ask("[bold]确认执行以上整理方案？[/]", default=False):
            console.print("[yellow]已取消。[/]")
            return

    # ── 步骤6: 执行 ──
    console.print()
    console.print(Panel.fit(
        "[bold]正在执行整理...[/]",
        title="[bold white] 步骤 5/6 · 执行整理 [/]",
        border_style="green",
    ))
    logs = execute_plan(plan, dry_run=False)
    print_execution_logs(logs)

    # ── 步骤6: 最终报告 ──
    # 重新扫描以获取最终状态
    with console.status("[bold green]生成最终报告..."):
        final_result = scan_directory(str(target), include_hidden=hidden)
    print_final_tree(target, final_result)

    console.print()
    console.print(Panel.fit(
        "[bold green]整理完成！[/]",
        border_style="green",
    ))


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--hidden", is_flag=True, help="包含隐藏文件")
def duplicates(directory, hidden):
    """仅检测重复文件"""
    target = Path(directory).expanduser().resolve()
    console.print(Panel.fit(
        f"[bold]正在扫描重复文件:[/] {target}",
        border_style="cyan",
    ))

    with console.status("[bold green]扫描中..."):
        result = scan_directory(str(target), include_hidden=hidden)

    if not result.duplicate_groups:
        console.print("[green]未发现重复文件。[/]")
        return

    console.print(f"\n发现 [bold red]{len(result.duplicate_groups)}[/] 组重复文件:\n")

    for gid, group in result.duplicate_groups.items():
        total_size = sum(f.size for f in group)
        console.print(f"[bold]组 {gid}[/] — {group[0].size_str} × {len(group)} = {total_size / 1024 / 1024:.1f} MB")
        for fi in sorted(group, key=lambda f: f.modified, reverse=True):
            tag = "[green]保留[/]" if fi == sorted(group, key=lambda f: f.modified, reverse=True)[0] else "[red]重复[/]"
            console.print(f"  {tag} {fi.name}")
            console.print(f"       [dim]{fi.path}[/]")
            console.print(f"       [dim]修改时间: {fi.modified.strftime('%Y-%m-%d %H:%M')}[/]")
        console.print()


def main():
    """入口点"""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断。[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
