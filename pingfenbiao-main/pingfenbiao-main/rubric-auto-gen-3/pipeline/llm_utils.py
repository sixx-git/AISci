"""
LLM 调用工具 — 封装 DashScope (OpenAI 兼容) API 调用与 JSON 解析。
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def call_llm(
    client,
    model: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    max_retries: int = 3,
) -> str:
    """
    调用 LLM 并返回文本响应。
    内置重试逻辑和指数退避。
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            return content.strip()

        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}, "
                          f"等待 {wait}s...")
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def call_llm_json(
    client,
    model: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.3,
    max_tokens: int = 8192,
    max_retries: int = 3,
) -> Any:
    """
    调用 LLM 并解析返回的 JSON。
    支持 markdown 代码块包裹的 JSON 和裸 JSON。
    """
    raw = call_llm(client, model, prompt, system, temperature, max_tokens, max_retries)
    return _parse_json(raw)


def _parse_json(text: str) -> Any:
    """
    从 LLM 响应中解析 JSON，处理常见的格式问题。
    """
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 [ 或 { 到最后一个 ] 或 }
    text = text.strip()
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"无法从 LLM 响应中解析 JSON:\n{text[:500]}...")


def call_llm_batch(
    client,
    model: str,
    prompts: list[dict],
    temperature: float = 0.3,
    max_retries: int = 3,
) -> list[str]:
    """
    批量调用 LLM（顺序执行，非并发）。
    prompts: [{"prompt": str, "system": str}, ...]
    """
    results = []
    for i, p in enumerate(prompts):
        logger.info(f"  批量调用 {i + 1}/{len(prompts)}...")
        result = call_llm(
            client, model,
            p["prompt"],
            p.get("system", ""),
            temperature,
            max_retries=max_retries,
        )
        results.append(result)
    return results
