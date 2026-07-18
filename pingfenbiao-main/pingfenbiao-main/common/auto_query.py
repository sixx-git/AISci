"""从文献自动生成 research query（三套生成器与 Web 共用）。"""
from __future__ import annotations

import logging
from typing import Any, List, Protocol

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = {
    "claim_verification": (
        "Based on the provided source documents, generate domain-level rubric criteria "
        "for evaluating claim verification reports in this research field."
    ),
    "data_analysis": (
        "Based on the provided source documents and data files, generate domain-level "
        "rubric criteria for data analysis reports in this research field."
    ),
    "literature_review": (
        "Based on the provided source documents, generate domain-level rubric criteria "
        "for scientific literature review reports in this research field."
    ),
}

TASK_LABELS = {
    "claim_verification": "Claim verification report",
    "data_analysis": "Data analysis report",
    "literature_review": "Scientific literature review report",
}

PROMPT_AUTO_QUERY = """\
You are an expert research analyst. Based ONLY on the source documents below, write ONE \
research question or task description that defines what a high-quality academic report \
in this domain should address.

Task type: {task_type_label}

Requirements:
1. Write in English, one concise paragraph (2-4 sentences)
2. Capture the core research problem, scope, and analytical goals implied by the sources
3. Suitable for generating evaluation rubric criteria — do NOT state a conclusion or verdict
4. Use domain-general language; do not copy paper-specific method names
5. Output ONLY the question text — no quotes, labels, or JSON

Source documents:
---
{summaries}
---
"""


class _SourceLike(Protocol):
    source_id: str
    file_name: str
    full_text: str


def _summarize_sources(sources: List[Any], max_chars: int = 12000) -> str:
    if not sources:
        return "(no sources)"
    per_source = max(2000, max_chars // len(sources))
    parts = []
    for s in sources:
        text = getattr(s, "full_text", "") or ""
        excerpt = text[:per_source]
        if len(text) > per_source:
            excerpt += f"\n... [truncated, {len(text)} chars total] ..."
        parts.append(
            f"### {getattr(s, 'source_id', '?')} — {getattr(s, 'file_name', '?')}\n{excerpt}"
        )
    return "\n\n".join(parts)


def auto_generate_query(
    sources: List[Any],
    task_type: str,
    config,
) -> str:
    """用 LLM 从文献摘要生成 query，失败则回退到默认描述。"""
    fallback = DEFAULT_QUERIES.get(task_type, DEFAULT_QUERIES["literature_review"])
    label = TASK_LABELS.get(task_type, task_type)

    try:
        from openai import OpenAI

        client = config.get_client()
        model = getattr(config, "extract_model", None) or getattr(
            config, "rubric_model", "qwen3.7-max"
        )
        summaries = _summarize_sources(sources)
        prompt = PROMPT_AUTO_QUERY.format(task_type_label=label, summaries=summaries)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You write precise research task descriptions. Output plain text only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        text = (response.choices[0].message.content or "").strip()
        # 去掉可能的引号包裹
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
            text = text[1:-1].strip()
        if len(text) >= 20:
            if getattr(config, "verbose", True):
                logger.info("Auto-generated query from sources:")
                logger.info(f"  {text[:300]}{'...' if len(text) > 300 else ''}")
            return text
    except Exception as e:
        logger.warning(f"Auto query generation failed ({e}), using default fallback")

    logger.info("Using default query fallback for task type: %s", task_type)
    return fallback


def ensure_query(
    query: str,
    sources: List[Any],
    task_type: str,
    config,
) -> str:
    """若 query 为空则从文献自动生成，否则返回用户输入。"""
    if query and query.strip():
        return query.strip()
    logger.info("No query provided — generating from source documents...")
    return auto_generate_query(sources, task_type, config)
