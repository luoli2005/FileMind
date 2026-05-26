"""安全的 API Key 管理 — .env 文件 + 环境变量 + 交互式输入"""

import os
from pathlib import Path

ENV_PATH = Path.home() / ".filemind" / ".env"

# Provider → 环境变量名映射
PROVIDER_ENV_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

# Provider → 显示名称
PROVIDER_NAMES = {
    "claude": "Claude (Anthropic)",
    "anthropic": "Claude (Anthropic)",
    "gpt": "GPT (OpenAI)",
    "openai": "GPT (OpenAI)",
    "deepseek": "DeepSeek",
}


def _load_env_file() -> dict:
    """从 ~/.filemind/.env 读取键值对"""
    env = {}
    if not ENV_PATH.exists():
        return env
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and value:
                        env[key] = value
    except Exception:
        pass
    return env


def _save_env_var(key: str, value: str):
    """追加一个键值对到 ~/.filemind/.env"""
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 读取现有内容，更新或追加
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def get_api_key(provider: str, prompt_if_missing: bool = True) -> str:
    """获取 API Key，按优先级：环境变量 > .env 文件 > 交互式输入"""

    provider = provider.lower()
    env_key = PROVIDER_ENV_KEYS.get(provider)
    if not env_key:
        raise ValueError(f"不支持的 provider: {provider}")

    # 1. 环境变量
    key = os.environ.get(env_key)
    if key:
        return key

    # 2. .env 文件
    env_file = _load_env_file()
    key = env_file.get(env_key)
    if key:
        # 同步到环境变量，后续调用不再读文件
        os.environ[env_key] = key
        return key

    # 3. 交互式输入
    if prompt_if_missing:
        provider_name = PROVIDER_NAMES.get(provider, provider)
        from rich.console import Console
        from rich.prompt import Prompt
        console = Console()
        console.print(f"\n[yellow]未找到 {provider_name} 的 API Key[/]")
        console.print(f"[dim]环境变量 {env_key} 未设置，.env 文件中也没有[/]")

        key = Prompt.ask(
            f"请输入 {provider_name} API Key",
            password=True,
        )
        if key:
            _save_env_var(env_key, key)
            os.environ[env_key] = key
            console.print(f"[green]已保存到 {ENV_PATH}[/]")
            return key

    return ""


def remove_api_key(provider: str):
    """从 .env 文件中移除指定 provider 的 API Key"""
    provider = provider.lower()
    env_key = PROVIDER_ENV_KEYS.get(provider)
    if not env_key:
        return

    if not ENV_PATH.exists():
        return

    lines = []
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = [l for l in lines if not l.strip().startswith(f"{env_key}=")]

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # 同步清除环境变量
    os.environ.pop(env_key, None)


def list_configured_keys() -> dict:
    """列出已配置的 API Key（脱敏显示）"""
    result = {}
    env_file = _load_env_file()

    for provider, env_key in PROVIDER_ENV_KEYS.items():
        if provider in ("anthropic", "openai"):
            continue  # 跳过别名

        key = os.environ.get(env_key) or env_file.get(env_key)
        if key:
            # 脱敏：显示前 8 位和后 4 位
            if len(key) > 12:
                masked = key[:8] + "..." + key[-4:]
            else:
                masked = key[:4] + "..."
            result[provider] = {
                "env_key": env_key,
                "masked": masked,
                "source": "env" if os.environ.get(env_key) else ".env",
            }
        else:
            result[provider] = {
                "env_key": env_key,
                "masked": "未配置",
                "source": "",
            }

    return result
