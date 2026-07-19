"""Chunk 级情境摘要打分（RCS，借鉴 PaperQA map_fxn_summary）。

对向量检索候选 chunk 生成 {summary, relevance_score:0-10}，按 cutoff 硬截断。
不引入 PaperQA / LiteLLM 运行时依赖。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

_RCS_SCHEMA = {
    "summary": "该片段说明联邦学习中合成数据导致的域偏移问题。",
    "relevance_score": 7,
}


def _settings() -> Tuple[bool, int, bool, bool]:
    from app.core.config import get_settings

    s = get_settings()
    return (
        bool(getattr(s, "LIT_RELEVANCE_GATE_ENABLED", True)),
        int(getattr(s, "LIT_CHUNK_SCORE_CUTOFF", 5) or 5),
        bool(getattr(s, "USE_MOCK_LLM", False)),
        bool((getattr(s, "QWEN_API_KEY", "") or "").strip()),
    )


def _heuristic_chunk_score(research_question: str, content: str, title: str = "") -> float:
    from app.skills.evidence_reasoning._utils import score_relevance

    text = f"{title}\n{content}".strip()
    if not text:
        return 0.0
    base = score_relevance(research_question, text)
    if base <= 0:
        return 0.0
    return round(min(10.0, max(1.0, base * 12.0)), 1)


def _score_one_chunk_llm(
    research_question: str,
    content: str,
    title: str = "",
) -> Tuple[str, float]:
    from app.services.qwen_client import qwen_structured_chat

    prompt = (
        "根据研究问题，为下列文献片段写一句情境摘要 summary，并给出整数 relevance_score（0-10）。\n"
        "若片段与问题无关，summary 置空字符串，relevance_score=0。\n"
        "只输出 JSON。\n\n"
        f"研究问题：{research_question}\n"
        f"文献标题：{title or '未知'}\n"
        f"片段原文：\n{(content or '')[:1200]}\n"
    )
    raw = qwen_structured_chat(
        prompt=prompt,
        schema_example=_RCS_SCHEMA,
        system_prompt="你是文献证据筛选助手，只输出 JSON。",
        temperature=0.1,
        prompt_version="lit_chunk_rcs_v1",
    )
    summary = str(raw.get("summary") or "").strip()
    try:
        score = float(raw.get("relevance_score", 0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(10.0, score))
    if not summary and score > 0:
        score = min(score, 2.0)
    return summary, score


def score_chunk(
    research_question: str,
    content: str,
    title: str = "",
    *,
    force_heuristic: bool = False,
) -> Tuple[str, float]:
    enabled, _, use_mock, has_key = _settings()
    if force_heuristic or not enabled or use_mock or not has_key:
        score = _heuristic_chunk_score(research_question, content, title)
        summary = (content or "")[:160] if score > 0 else ""
        return summary, score
    try:
        return _score_one_chunk_llm(research_question, content, title)
    except Exception as exc:
        logger.warning("[Chunk RCS] LLM 打分失败，回退启发式: %s", exc)
        score = _heuristic_chunk_score(research_question, content, title)
        summary = (content or "")[:160] if score > 0 else ""
        return summary, score


def rerank_search_results(
    research_question: str,
    search_results: Sequence[Any],
    *,
    cutoff: Optional[int] = None,
    keep_top_k: Optional[int] = None,
) -> Tuple[List[Any], Dict[str, Any]]:
    """对 SearchResult 列表做 RCS 打分截断；关闭门控时原样返回（可截断 keep_top_k）。"""
    enabled, default_cutoff, _, _ = _settings()
    cutoff = int(cutoff if cutoff is not None else default_cutoff)
    results = list(search_results or [])
    stats: Dict[str, Any] = {
        "enabled": enabled,
        "cutoff": cutoff,
        "candidate_count": len(results),
        "passed_count": len(results),
        "rejected_count": 0,
        "scores": [],
    }
    if not results:
        return [], stats

    if not enabled:
        kept = results[:keep_top_k] if keep_top_k else results
        stats["passed_count"] = len(kept)
        return kept, stats

    scored: List[Tuple[Any, float, str]] = []
    for r in results:
        content = getattr(r, "content", None) or (r.get("content") if isinstance(r, dict) else "") or ""
        title = (
            getattr(r, "source_title", None)
            or (r.get("source_title") if isinstance(r, dict) else None)
            or ""
        )
        summary, score = score_chunk(research_question, str(content), str(title))
        if hasattr(r, "relevance_score"):
            r.relevance_score = score
        if hasattr(r, "context_summary"):
            r.context_summary = summary
        scored.append((r, score, summary))
        stats["scores"].append(
            {
                "chunk_id": getattr(r, "chunk_id", None)
                or (r.get("chunk_id") if isinstance(r, dict) else None),
                "relevance_score": score,
                "summary": (summary or "")[:120],
            }
        )

    passed = [(r, s, sm) for r, s, sm in scored if s >= cutoff]
    passed.sort(key=lambda x: x[1], reverse=True)
    if keep_top_k is not None:
        passed = passed[:keep_top_k]

    kept = [r for r, _, _ in passed]
    stats["passed_count"] = len(kept)
    stats["rejected_count"] = max(0, len(results) - len(kept))
    logger.info(
        "[Chunk RCS] candidates=%s passed=%s rejected=%s cutoff=%s",
        len(results),
        stats["passed_count"],
        stats["rejected_count"],
        cutoff,
    )
    return kept, stats


class LiteratureChunkRerankSkill(BaseSkill):
    """对向量检索 chunk 做情境摘要打分并截断。"""

    name = "LiteratureChunkRerank"
    description = "PaperQA 风格 chunk RCS：情境摘要 + 0-10 相关性硬截断"
    source_reference = "PaperQA2 map_fxn_summary / relevance_score cutoff (arxiv:2312.07559)"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        research_question = (
            input_data.get("research_question")
            or context.get("research_question")
            or ""
        )
        chunks = input_data.get("chunks") or input_data.get("search_results") or []
        cutoff = input_data.get("cutoff")
        keep_top_k = input_data.get("keep_top_k") or input_data.get("top_k")

        kept, stats = rerank_search_results(
            str(research_question),
            chunks,
            cutoff=int(cutoff) if cutoff is not None else None,
            keep_top_k=int(keep_top_k) if keep_top_k is not None else None,
        )
        # 序列化便于 skill_outputs
        serialized = []
        for r in kept:
            if hasattr(r, "__dict__") or hasattr(r, "chunk_id"):
                serialized.append(
                    {
                        "chunk_id": getattr(r, "chunk_id", None),
                        "document_id": getattr(r, "document_id", None),
                        "content": (getattr(r, "content", None) or "")[:500],
                        "source_title": getattr(r, "source_title", None),
                        "similarity_score": getattr(r, "similarity_score", None),
                        "relevance_score": getattr(r, "relevance_score", None),
                        "context_summary": getattr(r, "context_summary", None),
                    }
                )
            elif isinstance(r, dict):
                serialized.append(r)

        result.data = {
            "chunks": serialized,
            "rerank_stats": stats,
        }
        if stats.get("enabled") and stats.get("passed_count", 0) == 0 and stats.get("candidate_count", 0) > 0:
            result.add_warning("所有候选 chunk 未通过 RCS 相关性截断")
        return result

