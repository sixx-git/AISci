"""论文级相关性门控 + 查询改写（借鉴 PaperQA，非运行时依赖）。

在推荐结果入库前对「标题+摘要」打 0–10 分并硬截断，同时从研究问题生成
3–5 条检索 query，供向量检索 / 补充检索使用。可通过 LIT_RELEVANCE_GATE_ENABLED 关闭。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_GATE_SCHEMA = {
    "papers": [
        {
            "index": 0,
            "relevance_score": 8,
            "reason": "与研究问题直接相关",
        }
    ]
}

_REWRITE_SCHEMA = {
    "search_queries": [
        "federated learning synthetic data",
        "联邦学习 合成数据 跌倒检测",
    ]
}


def _settings():
    from app.core.config import get_settings

    s = get_settings()
    return (
        bool(getattr(s, "LIT_RELEVANCE_GATE_ENABLED", True)),
        int(getattr(s, "LIT_PAPER_SCORE_CUTOFF", 6) or 6),
        bool(getattr(s, "USE_MOCK_LLM", False)),
        bool((getattr(s, "QWEN_API_KEY", "") or "").strip()),
    )


def _heuristic_paper_score(research_question: str, paper: Dict[str, Any]) -> float:
    from app.skills.evidence_reasoning._utils import score_relevance

    title = str(paper.get("title") or "")
    abstract = str(paper.get("abstract") or "")
    text = f"{title}\n{abstract}".strip()
    if not text:
        return 0.0
    # score_relevance ∈ [0,1] → 映射到约 0–10，有轻微重叠时不低于 3
    base = score_relevance(research_question, text)
    if base <= 0:
        return 0.0
    return round(min(10.0, max(1.0, base * 12.0)), 1)


def _heuristic_queries(research_question: str, research_domain: str = "") -> List[str]:
    from app.skills.evidence_reasoning._utils import tokenize

    tokens = list(tokenize(research_question))[:8]
    queries: List[str] = []
    if research_question.strip():
        queries.append(research_question.strip()[:200])
    domain = (research_domain or "").strip()
    if domain:
        queries.append(domain[:120])
    if len(tokens) >= 2:
        queries.append(" ".join(tokens[:5]))
    # 去重保序
    seen = set()
    out: List[str] = []
    for q in queries:
        key = q.lower()
        if key in seen or not q:
            continue
        seen.add(key)
        out.append(q)
    return out[:5]


def rewrite_search_queries(
    research_question: str,
    research_domain: str = "",
    *,
    existing_queries: Optional[List[str]] = None,
) -> List[str]:
    """从研究问题生成 3–5 条中英混合检索 query。

    若推荐阶段已给出足够 search_queries，直接复用并与启发式合并，不再额外调 LLM。
    """
    enabled, _, use_mock, has_key = _settings()
    rq = (research_question or "").strip()
    domain = (research_domain or "").strip()
    existing = [str(q).strip() for q in (existing_queries or []) if str(q).strip()]
    fallback = list(existing) + _heuristic_queries(rq, domain)

    # 推荐已带 ≥2 条 query：跳过改写 LLM
    if len(existing) >= 2:
        return _dedupe_queries(fallback)[:5]

    if not enabled or use_mock or not has_key or not rq:
        return _dedupe_queries(fallback)[:5]

    try:
        from app.services.qwen_client import qwen_structured_chat

        prompt = (
            "根据研究问题生成 3 到 5 条文献检索查询（可中英混合）。\n"
            "要求：覆盖核心概念、方法、应用场景；短句或关键词组合；不要解释。\n\n"
            f"研究问题：{rq}\n"
            f"研究领域：{domain or '未指定'}\n"
        )
        raw = qwen_structured_chat(
            prompt=prompt,
            schema_example=_REWRITE_SCHEMA,
            system_prompt="你是科研文献检索助手，只输出 JSON。",
            temperature=0.2,
            prompt_version="lit_query_rewrite_v1",
        )
        generated = [
            str(q).strip()
            for q in (raw.get("search_queries") or [])
            if str(q).strip()
        ]
        return _dedupe_queries(generated + fallback)[:5]
    except Exception as exc:
        logger.warning("[文献门控] 查询改写失败，使用启发式: %s", exc)
        return _dedupe_queries(fallback)[:5]


def _dedupe_queries(queries: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for q in queries:
        q = re.sub(r"\s+", " ", (q or "").strip())
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def _parse_existing_score(paper: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    """读取推荐阶段已写入的 relevance_score；无效则 None。"""
    raw = paper.get("relevance_score")
    if raw is None:
        raw = paper.get("recommend_relevance_score")
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return None
    if score != score:  # NaN
        return None
    score = max(0.0, min(10.0, score))
    reason = str(
        paper.get("relevance_reason")
        or paper.get("score_source")
        or "llm_recommend"
    )[:200]
    return score, reason


def _llm_score_papers(
    research_question: str,
    papers: List[Dict[str, Any]],
) -> Dict[int, Tuple[float, str]]:
    """批量打分；返回 index -> (score, reason)。失败则空 dict。"""
    if not papers:
        return {}
    try:
        from app.services.qwen_client import qwen_structured_chat

        lines = []
        for i, p in enumerate(papers):
            title = (p.get("title") or "")[:200]
            abstract = (p.get("abstract") or "")[:500]
            lines.append(f"[{i}] 标题: {title}\n摘要: {abstract or '(无摘要)'}")
        prompt = (
            "评估下列论文与研究问题的相关性。对每篇给出整数 relevance_score（0-10）与简短 reason。\n"
            "评分标准：10=直接回答问题核心；6-9=高度相关方法/数据/场景；"
            "3-5=弱相关或仅同领域；0-2=无关或标题党。\n"
            "只输出 JSON，papers 数组须覆盖全部 index。\n\n"
            f"研究问题：{research_question}\n\n"
            "候选论文：\n" + "\n\n".join(lines)
        )
        raw = qwen_structured_chat(
            prompt=prompt,
            schema_example=_GATE_SCHEMA,
            system_prompt="你是严格的文献相关性评审，只输出 JSON。",
            temperature=0.1,
            prompt_version="lit_paper_relevance_gate_v1",
        )
        scored: Dict[int, Tuple[float, str]] = {}
        for item in raw.get("papers") or []:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            try:
                score = float(item.get("relevance_score", 0))
            except (TypeError, ValueError):
                score = 0.0
            score = max(0.0, min(10.0, score))
            reason = str(item.get("reason") or "")[:200]
            scored[idx] = (score, reason)
        return scored
    except Exception as exc:
        logger.warning("[文献门控] LLM 论文打分失败，回退启发式: %s", exc)
        return {}


def score_and_gate_papers(
    research_question: str,
    papers: List[Dict[str, Any]],
    *,
    cutoff: Optional[int] = None,
) -> Dict[str, Any]:
    """对论文列表打分并按 cutoff 过滤。关闭门控时原样返回。

    若推荐阶段已写入 relevance_score，直接复用，不再单独调用门控 LLM。
    """
    enabled, default_cutoff, use_mock, has_key = _settings()
    cutoff = int(cutoff if cutoff is not None else default_cutoff)
    papers = [dict(p) for p in (papers or []) if isinstance(p, dict)]

    if not enabled:
        for p in papers:
            p.setdefault("gate_passed", True)
            p.setdefault("relevance_score", None)
        return {
            "enabled": False,
            "papers": papers,
            "passed": papers,
            "rejected": [],
            "cutoff": cutoff,
            "candidate_count": len(papers),
            "passed_count": len(papers),
            "rejected_count": 0,
            "score_source": "disabled",
        }

    prefilled: Dict[int, Tuple[float, str]] = {}
    missing_indices: List[int] = []
    for i, p in enumerate(papers):
        parsed = _parse_existing_score(p)
        if parsed is not None:
            prefilled[i] = parsed
        else:
            missing_indices.append(i)

    llm_scores: Dict[int, Tuple[float, str]] = {}
    score_source = "recommend"
    if missing_indices and not use_mock and has_key and research_question.strip():
        # 仅对缺分论文补一次批量门控；若全部缺分则打全量
        if len(missing_indices) == len(papers):
            llm_scores = _llm_score_papers(research_question, papers)
            score_source = "gate_llm"
        else:
            subset = [papers[i] for i in missing_indices]
            subset_scores = _llm_score_papers(research_question, subset)
            for local_i, pair in subset_scores.items():
                if 0 <= local_i < len(missing_indices):
                    llm_scores[missing_indices[local_i]] = pair
            score_source = "recommend+gate_llm"
    elif missing_indices:
        score_source = "recommend+heuristic" if prefilled else "heuristic"

    passed: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for i, p in enumerate(papers):
        if i in prefilled:
            score, reason = prefilled[i]
            p["score_source"] = p.get("score_source") or "llm_recommend"
        elif i in llm_scores:
            score, reason = llm_scores[i]
            p["score_source"] = "gate_llm"
        else:
            score = _heuristic_paper_score(research_question, p)
            reason = "heuristic_overlap"
            p["score_source"] = "heuristic"
        p["relevance_score"] = score
        if reason and not (p.get("relevance_reason") or "").strip():
            p["relevance_reason"] = reason
        p["gate_passed"] = score >= cutoff
        if p["gate_passed"]:
            passed.append(p)
        else:
            rejected.append(p)

    logger.info(
        "[文献门控] 论文筛选: candidates=%s passed=%s rejected=%s cutoff=%s source=%s prefilled=%s",
        len(papers),
        len(passed),
        len(rejected),
        cutoff,
        score_source,
        len(prefilled),
    )
    return {
        "enabled": True,
        "papers": papers,
        "passed": passed,
        "rejected": rejected,
        "cutoff": cutoff,
        "candidate_count": len(papers),
        "passed_count": len(passed),
        "rejected_count": len(rejected),
        "score_source": score_source,
    }


def apply_relevance_gate(
    research_question: str,
    recommendation_output: Optional[Dict[str, Any]],
    *,
    research_domain: str = "",
    cutoff: Optional[int] = None,
) -> Dict[str, Any]:
    """对推荐输出做查询改写 + 论文门控，写回 papers / search_queries / gate_stats。"""
    rec = dict(recommendation_output or {})
    domain = (research_domain or rec.get("research_domain") or "").strip()
    rq = (research_question or rec.get("research_question") or "").strip()

    rewritten = rewrite_search_queries(
        rq,
        domain,
        existing_queries=list(rec.get("search_queries") or []),
    )
    if rewritten:
        rec["search_queries"] = rewritten
        rec["rewritten_queries"] = rewritten

    gate = score_and_gate_papers(rq, list(rec.get("papers") or []), cutoff=cutoff)
    # 入库与下游只保留通过门控的论文；全量保留在 gate_stats 便于审计
    if gate.get("enabled"):
        rec["papers"] = gate["passed"]
        rec["verified_count"] = sum(
            1 for p in gate["passed"] if p.get("verification_status") == "verified"
        )
        rec["partial_count"] = sum(
            1 for p in gate["passed"] if p.get("verification_status") == "partial"
        )
        rec["unverified_count"] = sum(
            1 for p in gate["passed"] if p.get("verification_status") == "unverified"
        )
        rec["total"] = len(gate["passed"])

    rec["gate_stats"] = {
        "enabled": gate.get("enabled"),
        "cutoff": gate.get("cutoff"),
        "candidate_count": gate.get("candidate_count"),
        "passed_count": gate.get("passed_count"),
        "rejected_count": gate.get("rejected_count"),
        "score_source": gate.get("score_source"),
        "rejected_titles": [
            (p.get("title") or "")[:120] for p in (gate.get("rejected") or [])[:20]
        ],
        "rewritten_queries": rewritten,
    }
    return rec

