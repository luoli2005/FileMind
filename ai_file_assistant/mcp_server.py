"""MCP 工具服务器 — 供 Claude / OpenAI / 本地 Agent 调用"""

import json
from mcp.server.fastmcp import FastMCP

from .tools import (
    tool_scan,
    tool_move,
    tool_rename,
    tool_analyze_duplicates,
    tool_generate_report,
    tool_create_folder,
)

mcp = FastMCP("AI文件助手")


@mcp.tool()
def scan_directory(path: str) -> str:
    """扫描目录，返回文件列表、分类、价值评估和风险分析。

    这是所有文件操作的第一步。先扫描，再规划，最后执行。

    Args:
        path: 要扫描的目录路径
    """
    result = tool_scan(path)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def move_file(src: str, dst: str, force: bool = False) -> str:
    """移动文件到新位置。

    高风险操作（系统目录、活跃文件）会返回 requires_confirmation=true，
    需要 Agent 确认后带 force=True 重试。

    所有操作自动记录到 undo 日志，可随时撤销。

    Args:
        src: 源文件路径
        dst: 目标路径（可以是目录或完整文件路径）
        force: 高风险操作确认（默认 false）
    """
    result = tool_move(src, dst, force)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def rename_file(path: str, new_name: str, force: bool = False) -> str:
    """重命名文件。

    智能清理文件名：去除乱码、副本、FINAL 等垃圾后缀。
    高风险操作需 force=True 确认。

    Args:
        path: 文件路径
        new_name: 新文件名（仅文件名，不含路径）
        force: 高风险操作确认（默认 false）
    """
    result = tool_rename(path, new_name, force)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def analyze_duplicate_files(path: str) -> str:
    """检测目录中的重复文件，包括精确重复、相似图片和重复视频。

    三种检测模式：
    1. 精确重复：MD5 哈希完全相同的文件
    2. 相似图片：感知哈希 (pHash) 比对，识别裁剪、缩放、加水印后的副本
    3. 重复视频：首帧哈希 + 元数据（时长、分辨率）比对

    Args:
        path: 要检测的目录路径
    """
    result = tool_analyze_duplicates(path)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def generate_summary_report(path: str) -> str:
    """生成完整的目录分析报告。

    包含：文件分类统计、价值评估、用途推断、风险分析、
    重命名建议、整理策略摘要。

    Args:
        path: 要分析的目录路径
    """
    result = tool_generate_report(path)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def create_folder(path: str) -> str:
    """创建目录（递归创建父目录）。

    Args:
        path: 要创建的目录路径
    """
    result = tool_create_folder(path)
    return json.dumps(result, ensure_ascii=False, indent=2)


def run_stdio():
    """以 stdio 模式启动 MCP 服务器"""
    mcp.run(transport="stdio")


def run_sse(host: str = "0.0.0.0", port: int = 8080):
    """以 SSE 模式启动 MCP 服务器"""
    mcp.run(transport="sse", host=host, port=port)
