"""自主 Agent 循环 — 支持 Claude / GPT / DeepSeek"""

import json
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .config import get_config


# ── LLM Tool 定义（供所有 Provider 共用）──────────────────────

TOOLS = [
    {
        "name": "scan_directory",
        "description": "扫描目录，返回文件列表、分类、价值评估和风险分析。所有文件操作的第一步。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要扫描的目录路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "move_file",
        "description": "移动文件到新位置。高风险操作（系统目录、活跃文件）会返回 requires_confirmation=true，需要带 force=True 重试。",
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "源文件路径"},
                "dst": {"type": "string", "description": "目标路径（目录或完整文件路径）"},
                "force": {"type": "boolean", "description": "高风险操作确认", "default": False}
            },
            "required": ["src", "dst"]
        }
    },
    {
        "name": "rename_file",
        "description": "智能重命名文件。清理乱码、副本、FINAL 等垃圾后缀。高风险操作需 force=True 确认。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "new_name": {"type": "string", "description": "新文件名（仅文件名，不含路径）"},
                "force": {"type": "boolean", "description": "高风险操作确认", "default": False}
            },
            "required": ["path", "new_name"]
        }
    },
    {
        "name": "analyze_duplicate_files",
        "description": "检测目录中的重复文件，包括精确重复、相似图片和重复视频。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要检测的目录路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "generate_summary_report",
        "description": "生成完整的目录分析报告。包含分类统计、价值评估、用途推断、风险分析、重命名建议、整理策略摘要。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要分析的目录路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "create_folder",
        "description": "创建目录（递归创建父目录）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要创建的目录路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "get_learned_memory",
        "description": "查看 FileMind 从历史操作中学到的偏好（垃圾关键词、分类偏好、重命名模式、风险校准）。",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "record_feedback",
        "description": "显式记录用户反馈，教 FileMind 你的偏好。",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation_type": {
                    "type": "string",
                    "enum": ["junk_keyword", "keep_keyword", "category_preference",
                             "rename_pattern", "risk_decision", "purpose_keyword"],
                    "description": "操作类型"
                },
                "target": {"type": "string", "description": "关键词、模式或 'category|folder' 字符串"},
                "accepted": {"type": "boolean", "description": "是否接受"}
            },
            "required": ["operation_type", "target", "accepted"]
        }
    },
]


# ── OpenAI 格式工具定义 ──────────────────────────────────────

def _to_openai_tools(tools: list) -> list:
    """将 Anthropic 格式转为 OpenAI function calling 格式"""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            }
        }
        for t in tools
    ]


# ── 工具执行器 ──────────────────────────────────────────────

def _execute_tool(name: str, args: dict) -> dict:
    """调用 FileMind 工具"""
    from .tools import (
        tool_scan, tool_move, tool_rename,
        tool_analyze_duplicates, tool_generate_report,
        tool_create_folder, tool_get_memory, tool_record_feedback,
    )

    dispatch = {
        "scan_directory": lambda a: tool_scan(a["path"]),
        "move_file": lambda a: tool_move(a["src"], a["dst"], a.get("force", False)),
        "rename_file": lambda a: tool_rename(a["path"], a["new_name"], a.get("force", False)),
        "analyze_duplicate_files": lambda a: tool_analyze_duplicates(a["path"]),
        "generate_summary_report": lambda a: tool_generate_report(a["path"]),
        "create_folder": lambda a: tool_create_folder(a["path"]),
        "get_learned_memory": lambda a: tool_get_memory(),
        "record_feedback": lambda a: tool_record_feedback(
            a["operation_type"], a["target"], a["accepted"]
        ),
    }

    fn = dispatch.get(name)
    if not fn:
        return {"success": False, "error": f"未知工具: {name}"}
    try:
        return fn(args)
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Provider 抽象 ───────────────────────────────────────────

@dataclass
class LLMResponse:
    content: list = field(default_factory=list)  # text blocks + tool_use blocks
    stop_reason: str = ""  # "end_turn" or "tool_use"
    usage: dict = field(default_factory=dict)


@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class ToolResultBlock:
    type: str = "tool_result"
    tool_use_id: str = ""
    content: str = ""


class LLMProvider:
    """LLM Provider 基类"""

    def chat(self, messages: list, system: str = "") -> LLMResponse:
        raise NotImplementedError


class ClaudeProvider(LLMProvider):
    """Anthropic Claude"""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str = None):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("需要安装 anthropic: pip install anthropic")
        if not api_key:
            from .secrets import get_api_key
            api_key = get_api_key("claude")
        if not api_key:
            raise RuntimeError("未配置 Anthropic API Key")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def chat(self, messages: list, system: str = "") -> LLMResponse:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        result = LLMResponse(stop_reason=resp.stop_reason)
        for block in resp.content:
            if block.type == "text":
                result.content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                result.content.append(ToolUseBlock(
                    id=block.id, name=block.name, input=block.input
                ))
        result.usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
        return result


class OpenAIProvider(LLMProvider):
    """OpenAI GPT / DeepSeek（共用 OpenAI SDK）"""

    def __init__(self, model: str = "gpt-4o", api_key: str = None, base_url: str = None, provider_name: str = "gpt"):
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("需要安装 openai: pip install openai")
        if not api_key:
            from .secrets import get_api_key
            api_key = get_api_key(provider_name)
        if not api_key:
            raise RuntimeError(f"未配置 {provider_name} API Key")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self._tools = _to_openai_tools(TOOLS)

    def chat(self, messages: list, system: str = "") -> LLMResponse:
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if isinstance(content, str):
                oai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Convert from Anthropic format
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append({"type": "text", "text": block["text"]})
                        elif block.get("type") == "tool_use":
                            parts.append({
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"], ensure_ascii=False),
                                }
                            })
                        elif block.get("type") == "tool_result":
                            parts.append({
                                "type": "function",
                                "name": block.get("name", ""),
                                "content": block.get("content", ""),
                            })
                    elif hasattr(block, "type"):
                        if block.type == "text":
                            parts.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            parts.append({
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input, ensure_ascii=False),
                                }
                            })
                        elif block.type == "tool_result":
                            parts.append({
                                "type": "function",
                                "name": getattr(block, "name", ""),
                                "content": block.content,
                            })
                if len(parts) == 1 and parts[0].get("type") == "text":
                    oai_messages.append({"role": role, "content": parts[0]["text"]})
                else:
                    oai_messages.append({"role": role, "content": parts})

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            tools=self._tools,
            max_tokens=4096,
        )

        choice = resp.choices[0]
        result = LLMResponse(stop_reason="end_turn" if choice.finish_reason == "stop" else "tool_use")

        if choice.message.content:
            result.content.append(TextBlock(text=choice.message.content))

        if choice.message.tool_calls:
            result.stop_reason = "tool_use"
            for tc in choice.message.tool_calls:
                result.content.append(ToolUseBlock(
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments),
                ))

        if resp.usage:
            result.usage = {
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            }
        return result


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek（通过 OpenAI 兼容 API）"""

    def __init__(self, model: str = "deepseek-chat", api_key: str = None):
        super().__init__(
            model=model,
            api_key=api_key,
            base_url="https://api.deepseek.com",
            provider_name="deepseek",
        )


# ── Provider 工厂 ───────────────────────────────────────────

def create_provider(provider: str = "claude", model: str = None, api_key: str = None) -> LLMProvider:
    """创建 LLM Provider"""
    provider = provider.lower()

    if provider in ("claude", "anthropic"):
        return ClaudeProvider(model=model or "claude-sonnet-4-6", api_key=api_key)
    elif provider in ("gpt", "openai"):
        return OpenAIProvider(model=model or "gpt-4o", api_key=api_key)
    elif provider == "deepseek":
        return DeepSeekProvider(model=model or "deepseek-chat", api_key=api_key)
    else:
        raise ValueError(f"不支持的 provider: {provider}，可选: claude, gpt, deepseek")


# ── 系统提示 ────────────────────────────────────────────────

SYSTEM_PROMPT = """你是 FileMind，一个专业的 AI 文件管理助手。

## 能力
你可以通过工具调用来管理用户的文件：扫描分析、智能分类、重命名、检测重复、执行整理。

## 工作流程
1. 先用 `get_learned_memory` 了解用户的历史偏好
2. 用 `scan_directory` 扫描目标目录
3. 分析扫描结果，制定整理策略
4. 逐步执行：先创建目录，再移动/重命名文件
5. 遇到高风险操作（requires_confirmation=true），向用户说明风险并请求确认
6. 执行完成后，用 `record_feedback` 记录关键决策
7. 生成最终报告

## 安全规则
- 绝不删除文件，只移动
- 高风险操作必须先告知用户，等用户确认后再用 force=True 执行
- 重复文件移到 Duplicates/ 目录
- 每次操作前检查目标路径是否合理

## 风格
- 用中文回复
- 简洁明了，不要过度解释
- 执行前说明计划，执行后汇报结果
- 遇到错误自行调整策略重试"""


# ── Agent 主循环 ────────────────────────────────────────────

@dataclass
class AgentResult:
    success: bool = True
    total_rounds: int = 0
    total_tokens: int = 0
    summary: str = ""
    logs: list = field(default_factory=list)


def run_agent(
    target_dir: str,
    goal: str = "整理这个目录，清理垃圾文件，分类归档",
    provider: str = "claude",
    model: str = None,
    api_key: str = None,
    max_rounds: int = 20,
    auto_confirm: bool = False,
    console=None,
) -> AgentResult:
    """运行自主 Agent"""

    llm = create_provider(provider, model, api_key)
    result = AgentResult()

    messages = [{
        "role": "user",
        "content": f"目标目录: {target_dir}\n\n任务目标: {goal}\n\n请开始执行。"
    }]

    total_input_tokens = 0
    total_output_tokens = 0

    for round_num in range(1, max_rounds + 1):
        result.total_rounds = round_num

        if console:
            console.print(f"\n[dim]── 第 {round_num} 轮 ──[/]")

        try:
            response = llm.chat(messages, system=SYSTEM_PROMPT)
        except Exception as e:
            result.success = False
            result.summary = f"LLM 调用失败: {e}"
            result.logs.append(f"[ERROR] {e}")
            break

        total_input_tokens += response.usage.get("input_tokens", 0)
        total_output_tokens += response.usage.get("output_tokens", 0)

        # 显示 LLM 输出
        for block in response.content:
            if isinstance(block, TextBlock) and block.text.strip():
                if console:
                    console.print(f"\n[bold cyan]Agent:[/]\n{block.text}")
                result.logs.append(f"[Agent] {block.text}")

        # 检查是否完成
        if response.stop_reason == "end_turn":
            # 提取最终摘要
            for block in response.content:
                if isinstance(block, TextBlock):
                    result.summary = block.text
            break

        # 执行工具调用
        tool_results_content = []
        for block in response.content:
            if not isinstance(block, ToolUseBlock):
                continue

            if console:
                console.print(f"  [dim]🔧 {block.name}({json.dumps(block.input, ensure_ascii=False)[:120]})[/]")

            tool_result = _execute_tool(block.name, block.input)

            # 高风险操作拦截
            if not auto_confirm and tool_result.get("requires_confirmation"):
                if console:
                    console.print(f"  [bold yellow]⚠ 高风险操作，需要确认[/]")
                    console.print(f"  [yellow]{tool_result.get('warnings', [])}[/]")
                    from rich.prompt import Confirm
                    if not Confirm.ask("  确认执行？", default=False):
                        tool_result = {
                            "success": False,
                            "error": "用户拒绝了此高风险操作",
                            "user_declined": True,
                        }

            result_json = json.dumps(tool_result, ensure_ascii=False, indent=2)
            tool_results_content.append(ToolResultBlock(
                tool_use_id=block.id,
                content=result_json,
            ))

            if console:
                status = "✅" if tool_result.get("success") else "❌"
                console.print(f"  {status} {block.name}")

            result.logs.append(f"[Tool] {block.name} -> {'success' if tool_result.get('success') else 'failed'}")

        # 构造下一轮消息
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results_content})

    result.total_tokens = total_input_tokens + total_output_tokens
    if console:
        console.print(f"\n[dim]Token 消耗: {total_input_tokens} in + {total_output_tokens} out = {result.total_tokens} total[/]")

    return result
