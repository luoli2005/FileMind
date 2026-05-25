"""AI 文件助手 v2 — 命令行入口"""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt

from .scanner import scan_directory
from .organizer import build_organize_plan, execute_plan
from .config import get_config, init_config, load_config, save_config, CONFIG_PATH
from .undo import (
    create_session, save_session, list_sessions, undo_session, undo_last,
)
from .reporter import (
    print_agent_greeting, print_scan_report, print_analysis_insights,
    print_strategy_explanation, print_execution_logs, print_final_tree,
    print_undo_history, print_undo_result, print_risk_warning,
)

console = Console()

BANNER = """
╔══════════════════════════════════════════════╗
║          AI 文件助手 v2.1.0                  ║
║      智能文件管理 Agent · 安全可靠           ║
╚══════════════════════════════════════════════╝
"""


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="2.0.0", prog_name="AI 文件助手")
def cli(ctx):
    """AI 文件助手 — 智能文件管理 Agent

    帮助你自动扫描、分析、分类、重命名和整理文件。

    \b
    使用示例:
      python -m ai_file_assistant agent ~/Downloads
      python -m ai_file_assistant scan ~/Downloads
      python -m ai_file_assistant organize ~/Downloads --dry-run
      python -m ai_file_assistant undo --list
      python -m ai_file_assistant config --init
    """
    if ctx.invoked_subcommand is None:
        console.print(Panel(BANNER, border_style="cyan"))
        console.print(ctx.get_help())


# ── Agent 命令（v2 主入口）──────────────────────────────────

@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--hidden", is_flag=True, help="包含隐藏文件")
@click.option("--config", "config_path", type=click.Path(), help="自定义配置文件路径")
def agent(directory, hidden, config_path):
    """启动 AI 文件助手（交互模式）"""
    target = Path(directory).expanduser().resolve()
    config = load_config(Path(config_path)) if config_path else get_config()

    # 步骤 1: 问候
    print_agent_greeting(target)

    # 步骤 2: 扫描
    console.print(Panel.fit(
        f"[bold]正在扫描:[/] {target}",
        title="[bold white] 步骤 1 · 扫描目录 [/]",
        border_style="cyan",
    ))
    with console.status("[bold green]扫描中..."):
        result = scan_directory(str(target), include_hidden=hidden, config=config)

    if result.total_count == 0:
        console.print("[yellow]目录为空，无需整理。[/]")
        return

    # 步骤 3: 扫描报告 + 分析洞察
    print_scan_report(result)
    print_analysis_insights(result)

    # 步骤 4: 生成方案
    plan = build_organize_plan(result, config)
    print_strategy_explanation(plan)

    total_ops = len(plan.actions) + len(plan.rename_actions) + len(plan.duplicate_actions)
    if total_ops == 0:
        console.print("[green]目录已经很整洁，无需整理！[/]")
        return

    # 步骤 5: 交互菜单
    console.print()
    console.print("[bold]请选择操作:[/]")
    console.print("  [cyan][1][/] 执行完整整理 [dim](推荐)[/]")
    console.print("  [cyan][2][/] 仅预览 (dry-run)")
    console.print("  [cyan][3][/] 仅重命名文件")
    console.print("  [cyan][4][/] 仅处理重复文件")
    console.print("  [cyan][5][/] 查看历史操作 & 撤销")
    console.print("  [cyan][0][/] 退出")

    choice = IntPrompt.ask("\n请选择", default=1, choices=["0", "1", "2", "3", "4", "5"])

    if choice == 0:
        console.print("[dim]已退出。[/]")
        return
    elif choice == 5:
        _handle_undo_menu(target)
        return

    # 步骤 6: 风险确认
    print_risk_warning(plan)

    if choice == 2:
        console.print("\n[bold cyan]🔍 预览模式 (--dry-run)，不会执行任何操作[/]\n")
        logs = execute_plan(plan, dry_run=True)
        print_execution_logs(logs)
        return

    if not Confirm.ask("[bold]确认执行以上整理方案？[/]", default=False):
        console.print("[yellow]已取消。[/]")
        return

    # 步骤 7: 执行
    undo_sess = create_session(str(target))
    logs = execute_plan(plan, dry_run=False, undo_session=undo_sess)
    save_session(undo_sess)
    print_execution_logs(logs, session_id=undo_sess.session_id)

    # 步骤 8: 最终报告
    with console.status("[bold green]生成最终报告..."):
        final_result = scan_directory(str(target), include_hidden=hidden, config=config, skip_analysis=True)
    print_final_tree(target, final_result)

    console.print()
    console.print(Panel.fit("[bold green]整理完成！[/]", border_style="green"))


def _handle_undo_menu(target):
    """交互式撤销菜单"""
    sessions = list_sessions(str(target))
    print_undo_history(sessions)

    if not sessions:
        return

    session_id = input("\n请输入要撤销的会话 ID（留空取消）: ").strip()
    if not session_id:
        console.print("[dim]已取消。[/]")
        return

    if Confirm.ask(f"[bold]确认撤销会话 {session_id}？[/]", default=False):
        logs = undo_session(session_id)
        print_undo_result(logs)


# ── Scan 命令 ─────────────────────────────────────────────

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
    print_analysis_insights(result)


# ── Organize 命令 ─────────────────────────────────────────

@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--dry-run", is_flag=True, help="仅预览，不执行操作")
@click.option("--hidden", is_flag=True, help="包含隐藏文件")
@click.option("--yes", "-y", is_flag=True, help="跳过确认，直接执行")
def organize(directory, dry_run, hidden, yes):
    """扫描、规划并整理目录（完整流程）"""
    target = Path(directory).expanduser().resolve()
    config = get_config()

    console.print(Panel.fit(
        f"[bold]正在扫描:[/] {target}",
        title="[bold white] 步骤 1 · 扫描目录 [/]",
        border_style="cyan",
    ))
    with console.status("[bold green]扫描中..."):
        result = scan_directory(str(target), include_hidden=hidden, config=config)

    print_scan_report(result)
    print_analysis_insights(result)

    if result.total_count == 0:
        console.print("[yellow]目录为空，无需整理。[/]")
        return

    plan = build_organize_plan(result, config)
    print_strategy_explanation(plan)

    total_ops = len(plan.actions) + len(plan.rename_actions) + len(plan.duplicate_actions)
    if total_ops == 0:
        console.print("[green]目录已经很整洁，无需整理！[/]")
        return

    print_risk_warning(plan)

    if dry_run:
        console.print("\n[bold cyan]🔍 预览模式，不会执行任何操作[/]\n")
        logs = execute_plan(plan, dry_run=True)
        print_execution_logs(logs)
        return

    if not yes:
        console.print()
        if not Confirm.ask("[bold]确认执行以上整理方案？[/]", default=False):
            console.print("[yellow]已取消。[/]")
            return

    undo_sess = create_session(str(target))
    logs = execute_plan(plan, dry_run=False, undo_session=undo_sess)
    save_session(undo_sess)
    print_execution_logs(logs, session_id=undo_sess.session_id)

    with console.status("[bold green]生成最终报告..."):
        final_result = scan_directory(str(target), include_hidden=hidden, config=config, skip_analysis=True)
    print_final_tree(target, final_result)

    console.print()
    console.print(Panel.fit("[bold green]整理完成！[/]", border_style="green"))


# ── Duplicates 命令 ───────────────────────────────────────

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
        console.print(f"[bold]组 {gid}[/] — {group[0].size_str} x {len(group)} = {format_size(total_size)}")
        for fi in sorted(group, key=lambda f: f.modified, reverse=True):
            tag = "[green]保留[/]" if fi == sorted(group, key=lambda f: f.modified, reverse=True)[0] else "[red]重复[/]"
            console.print(f"  {tag} {fi.name}")
            console.print(f"       [dim]{fi.path}[/]")
            console.print(f"       [dim]修改时间: {fi.modified.strftime('%Y-%m-%d %H:%M')}[/]")
        console.print()


# ── Undo 命令 ─────────────────────────────────────────────

@cli.command()
@click.argument("directory", required=False, type=click.Path(exists=True, file_okay=False))
@click.option("--session", "-s", "session_id", help="指定撤销会话 ID")
@click.option("--list", "list_sessions_flag", is_flag=True, help="列出可撤销的操作")
@click.option("--dry-run", is_flag=True)
def undo(directory, session_id, list_sessions_flag, dry_run):
    """撤销之前的整理操作"""
    if list_sessions_flag:
        sessions = list_sessions(str(Path(directory).resolve()) if directory else None)
        print_undo_history(sessions)
        return

    if session_id:
        console.print(f"[bold]正在撤销会话 {session_id}...[/]")
        logs = undo_session(session_id, dry_run=dry_run)
        print_undo_result(logs)
        return

    if directory:
        target = str(Path(directory).resolve())
        console.print(f"[bold]正在撤销 {target} 的最近操作...[/]")
        logs = undo_last(target, dry_run=dry_run)
        print_undo_result(logs)
        return

    # 无参数：列出所有会话
    sessions = list_sessions()
    print_undo_history(sessions)
    if sessions:
        sid = input("\n请输入要撤销的会话 ID（留空取消）: ").strip()
        if sid:
            logs = undo_session(sid, dry_run=dry_run)
            print_undo_result(logs)


# ── Config 命令 ───────────────────────────────────────────

@cli.command()
@click.option("--init", "init_flag", is_flag=True, help="初始化默认配置")
@click.option("--show", "show_flag", is_flag=True, help="显示当前配置")
@click.option("--edit", "edit_flag", is_flag=True, help="在编辑器中打开配置文件")
def config(init_flag, show_flag, edit_flag):
    """管理配置文件"""
    if init_flag:
        path = init_config()
        console.print(f"[green]配置已初始化:[/] {path}")
        return

    if show_flag:
        cfg = get_config()
        console.print(f"[bold]配置文件:[/] {CONFIG_PATH}")
        console.print(f"[bold]存在:[/] {'是' if CONFIG_PATH.exists() else '否'}")
        console.print()
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                console.print(f.read())
        else:
            console.print("[dim]使用默认配置。运行 config --init 创建配置文件。[/]")
        return

    if edit_flag:
        import subprocess
        init_config()
        editor = "nano"
        subprocess.run([editor, str(CONFIG_PATH)])
        return

    # 无参数：显示帮助
    console.print("[bold]配置命令:[/]")
    console.print("  python -m ai_file_assistant config --init   初始化默认配置")
    console.print("  python -m ai_file_assistant config --show   显示当前配置")
    console.print("  python -m ai_file_assistant config --edit   编辑配置文件")
    console.print()
    console.print(f"[dim]配置文件路径: {CONFIG_PATH}[/]")


# ── Serve 命令 ────────────────────────────────────────────

@cli.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="传输协议")
@click.option("--port", default=8080, help="SSE 模式端口")
@click.option("--host", default="0.0.0.0", help="SSE 模式绑定地址")
def serve(transport, port, host):
    """启动 MCP 工具服务器（供 Claude / OpenAI / Agent 调用）"""
    from .mcp_server import run_stdio, run_sse

    if transport == "sse":
        console.print(Panel.fit(
            f"[bold]MCP 服务器启动中...[/]\n"
            f"传输: SSE\n"
            f"地址: http://{host}:{port}\n\n"
            f"[dim]供 Browser Use / HTTP 客户端调用[/]",
            border_style="green",
        ))
        run_sse(host=host, port=port)
    else:
        console.print(Panel.fit(
            "[bold]MCP 服务器启动中...[/]\n"
            "传输: stdio\n\n"
            "[dim]供 Claude / OpenAI / 本地 Agent 调用[/]",
            border_style="green",
        ))
        run_stdio()


# ── 入口 ──────────────────────────────────────────────────

def main():
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
