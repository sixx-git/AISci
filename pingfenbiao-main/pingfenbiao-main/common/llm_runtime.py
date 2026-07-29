"""
评分用 LLM 调用（支持 DashScope / Qwen 显式前缀缓存）。

跨 batch 复用报告：将长报告放在带 cache_control 的稳定 system 前缀中，
后续请求只变化 user 侧的评分项，命中显式/隐式 context cache 以降本。
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def parse_llm_json(text: str) -> Any:
    """从 LLM 响应中解析 JSON（兼容 markdown 代码块）。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    text = text.strip()
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"无法从 LLM 响应中解析 JSON:\n{text[:500]}...")


def extract_usage_stats(response: Any) -> dict[str, Any]:
    """从 OpenAI 兼容响应提取 token / cache 统计。"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    out: dict[str, Any] = {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        out["cached_tokens"] = getattr(details, "cached_tokens", None)
        out["cache_creation_input_tokens"] = getattr(
            details, "cache_creation_input_tokens", None
        )
    # 部分 SDK 把 cached_tokens 挂在 usage 根上
    if out.get("cached_tokens") is None:
        out["cached_tokens"] = getattr(usage, "cached_tokens", None)
    return {k: v for k, v in out.items() if v is not None}


def _strip_cache_control(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """去掉 cache_control，兼容不支持显式缓存的模型。"""
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict):
                    new_blocks.append(
                        {k: v for k, v in block.items() if k != "cache_control"}
                    )
                else:
                    new_blocks.append(block)
            if (
                len(new_blocks) == 1
                and isinstance(new_blocks[0], dict)
                and new_blocks[0].get("type") == "text"
                and "text" in new_blocks[0]
                and set(new_blocks[0].keys()) <= {"type", "text"}
            ):
                cleaned.append({"role": msg["role"], "content": new_blocks[0]["text"]})
            else:
                cleaned.append({"role": msg["role"], "content": new_blocks})
        else:
            cleaned.append(dict(msg))
    return cleaned


def call_llm_messages(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    max_retries: int = 3,
    allow_cache_control_fallback: bool = True,
) -> tuple[str, dict[str, Any]]:
    """
    以 messages 数组调用 LLM。

    Returns:
        (content, meta) — meta 含 usage、是否回退去掉 cache_control。
    """
    meta: dict[str, Any] = {
        "cache_control_used": False,
        "cache_control_fallback": False,
        "usage": {},
    }
    last_error: Exception | None = None
    active = messages

    # 检测是否带了 cache_control
    def _has_cache_control(msgs: list[dict[str, Any]]) -> bool:
        for m in msgs:
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and "cache_control" in b:
                        return True
        return False

    for attempt in range(max_retries):
        try:
            meta["cache_control_used"] = _has_cache_control(active)
            response = client.chat.completions.create(
                model=model,
                messages=active,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = (response.choices[0].message.content or "").strip()
            meta["usage"] = extract_usage_stats(response)
            return content, meta
        except Exception as e:
            last_error = e
            err_text = str(e).lower()
            # 显式缓存不被模型/网关接受时，去掉 cache_control 再试
            if (
                allow_cache_control_fallback
                and _has_cache_control(active)
                and any(
                    k in err_text
                    for k in (
                        "cache_control",
                        "cache control",
                        "unknown field",
                        "extra inputs",
                        "invalid",
                        "not support",
                        "unsupported",
                    )
                )
            ):
                logger.warning("显式 cache_control 不被接受，回退为普通 messages: %s", e)
                active = _strip_cache_control(messages)
                meta["cache_control_fallback"] = True
                continue

            wait = 2**attempt
            logger.warning(
                "LLM 调用失败 (尝试 %s/%s): %s, 等待 %ss...",
                attempt + 1,
                max_retries,
                e,
                wait,
            )
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise

    raise last_error or RuntimeError("LLM 调用失败")


def call_llm_json_messages(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    max_retries: int = 3,
) -> tuple[Any, dict[str, Any]]:
    """messages 调用并解析 JSON，返回 (parsed, call_meta)。"""
    raw, meta = call_llm_messages(
        client,
        model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )
    return parse_llm_json(raw), meta
