"""统一解析 DashScope / Qwen API Key，避免各处逻辑不一致。"""
from __future__ import annotations

import os
from pathlib import Path

_KEY_NAMES = ("DASHSCOPE_API_KEY", "QWEN_API_KEY")


def _strip_value(raw: str) -> str:
    return (raw or "").strip().strip('"').strip("'")


def _read_keys_from_env_file(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return found
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name in _KEY_NAMES:
            val = _strip_value(value)
            if val and name not in found:
                found[name] = val
    return found


def resolve_dashscope_api_key(
    explicit: str = "",
    *,
    package_root: Path | None = None,
) -> tuple[str, str]:
    """解析可用的 DashScope 兼容 API Key。

    优先级（兼顾 AISci 主项目常用 QWEN_API_KEY，与 pingfenbiao 的 DASHSCOPE_API_KEY）：
      1. 表单/调用方显式传入
      2. 进程环境变量 DASHSCOPE_API_KEY、QWEN_API_KEY
      3. AISci 仓库根目录 .env（优先 QWEN_API_KEY）
      4. pingfenbiao 包内各 .env（DASHSCOPE 优先）

    Returns:
        (api_key, source_label)；找不到时 api_key 为空字符串。
    """
    explicit = _strip_value(explicit)
    if explicit:
        return explicit, "form"

    for name in _KEY_NAMES:
        val = _strip_value(os.environ.get(name, ""))
        if val:
            return val, f"env:{name}"

    root = package_root
    if root is None:
        root = Path(__file__).resolve().parent.parent

    aisci_env = root.parent.parent / ".env"
    aisci_keys = _read_keys_from_env_file(aisci_env)
    for name in ("QWEN_API_KEY", "DASHSCOPE_API_KEY"):
        if aisci_keys.get(name):
            return aisci_keys[name], f"file:AISci/.env:{name}"

    candidates = [
        root / ".env",
        root / "rubric-auto-gen" / ".env",
        root / "rubric-auto-gen-2" / ".env",
        root / "rubric-auto-gen-3" / ".env",
    ]
    for path in candidates:
        keys = _read_keys_from_env_file(path)
        for name in _KEY_NAMES:
            if keys.get(name):
                return keys[name], f"file:{path.name}:{name}"

    return "", "missing"
