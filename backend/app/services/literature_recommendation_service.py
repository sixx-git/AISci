"""网页式文献推荐：用户问题 + 研究领域 → LLM 推荐 → API 校验 → 可选补搜。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.literature_search_utils import normalize_api_search_query
from app.services.paper_verification_service import verify_recommended_papers
from app.services.prompt_loader import get_prompt_loader
from app.services.qwen_client import qwen_structured_chat
from app.skills.literature.search_papers_skill import SearchPapersSkill

logger = logging.getLogger(__name__)


def _coerce_relevance_score(raw: Any) -> Optional[float]:
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return None
    if score != score:  # NaN
        return None
    return max(0.0, min(10.0, score))


def _settings() -> tuple[int, int, bool, bool]:
    s = get_settings()
    return (
        int(getattr(s, "LITERATURE_RECOMMEND_MAX", 12) or 12),
        int(getattr(s, "LITERATURE_MIN_VERIFIED", 4) or 4),
        bool(getattr(s, "LITERATURE_SUPPLEMENT_API", True)),
        bool(getattr(s, "LITERATURE_IMPORT_UNVERIFIED", False)),
    )


def llm_recommend_papers(
    research_question: str,
    research_domain: str,
    *,
    max_papers: int,
) -> Dict[str, Any]:
    settings = get_settings()
    if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
        return {"papers": [], "subtopics": [], "rationale": "LLM 不可用", "skipped": True}

    rq = (research_question or "").strip()
    domain = (research_domain or "").strip() or "未指定"

    loader = get_prompt_loader()
    prompt = loader.render_template(
        "literature_recommendation",
        {
            "research_question": rq,
            "research_domain": domain,
            "max_papers": max_papers,
        },
    )
    schema = {
        "subtopics": [{"label": "example topic", "summary": "what it addresses"}],
        "papers": [
            {
                "title": "Example Paper Title",
                "authors": ["Author A"],
                "year": 2023,
                "venue": "Conference",
                "doi": "10.1234/example",
                "arxiv_id": "",
                "subtopic_labels": ["example topic"],
                "relevance_score": 8,
                "relevance_reason": "Directly relevant to the research question",
                "category": "survey",
            }
        ],
        "rationale": "brief strategy",
        "search_queries": ["federated learning synthetic data"],
    }
    try:
        result = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            temperature=0.25,
            prompt_version="literature_recommend_web_v4",
        )
        if not isinstance(result, dict):
            return {"papers": [], "subtopics": [], "rationale": "LLM 返回格式异常"}
        papers = result.get("papers") or []
        cleaned: List[Dict[str, Any]] = []
        for p in papers:
            if not isinstance(p, dict):
                continue
            if not str(p.get("title") or "").strip():
                continue
            item = dict(p)
            score = _coerce_relevance_score(item.get("relevance_score"))
            if score is not None:
                item["relevance_score"] = score
                item["recommend_relevance_score"] = score
                item["score_source"] = "llm_recommend"
            cleaned.append(item)
        queries = [
            str(q).strip()
            for q in (result.get("search_queries") or [])
            if str(q).strip()
        ]
        return {
            "papers": cleaned[:max_papers],
            "subtopics": result.get("subtopics") or [],
            "rationale": str(result.get("rationale") or ""),
            "search_queries": queries[:3],
        }
    except Exception as exc:
        logger.warning("LLM 文献推荐失败: %s", exc)
        return {"papers": [], "subtopics": [], "rationale": str(exc)[:200], "error": str(exc)[:200]}


async def _supplement_by_search_queries(
    search_queries: List[str],
    *,
    existing_keys: set[str],
    max_add: int = 3,
) -> List[Dict[str, Any]]:
    skill = SearchPapersSkill()
    added: List[Dict[str, Any]] = []

    for raw_q in search_queries:
        if len(added) >= max_add:
            break
        query = normalize_api_search_query(raw_q) or raw_q.strip()
        if not query:
            continue
        try:
            result = await skill.run(
                input_data={
                    "research_question": query,
                    "keywords": [],
                    "max_results": 3,
                    "sources": ["openalex", "semantic_scholar"],
                },
                context={"stage": "literature_supplement", "query": query[:80]},
            )
            for p in (result.data or {}).get("papers") or []:
                key = skill._generate_paper_key(p)
                if key and key in existing_keys:
                    continue
                if key:
                    existing_keys.add(key)
                item = dict(p)
                item["relevance_reason"] = f"API 补搜: {query[:100]}"
                item["category"] = "api_supplement"
                item["subtopic_labels"] = ["api_supplement"]
                added.append(item)
                if len(added) >= max_add:
                    break
        except Exception as exc:
            logger.warning("API 补搜失败 %s: %s", query[:60], exc)

    return added


def _paper_keys(papers: List[Dict[str, Any]]) -> set[str]:
    skill = SearchPapersSkill()
    keys: set[str] = set()
    for p in papers:
        k = skill._generate_paper_key(p)
        if k:
            keys.add(k)
    return keys


def _count_importable(papers: List[Dict[str, Any]]) -> int:
    return sum(1 for p in papers if p.get("verification_status") in ("verified", "partial"))


async def run_literature_recommendation(
    research_question: str,
    research_domain: str = "",
    *,
    max_papers: Optional[int] = None,
    min_verified: Optional[int] = None,
    supplement_api: Optional[bool] = None,
) -> Dict[str, Any]:
    max_p, min_v, sup_default, _ = _settings()
    max_papers = max_papers if max_papers is not None else max_p
    min_verified = min_verified if min_verified is not None else min_v
    supplement_api = supplement_api if supplement_api is not None else sup_default

    rq = (research_question or "").strip()
    domain = (research_domain or "").strip()

    rec = llm_recommend_papers(rq, domain, max_papers=max_papers)
    raw_papers = rec.get("papers") or []

    verified_papers = await verify_recommended_papers(raw_papers)

    supplement_used = False
    if supplement_api and _count_importable(verified_papers) < min_verified:
        existing = _paper_keys(verified_papers)
        extra = await _supplement_by_search_queries(
            rec.get("search_queries") or [],
            existing_keys=existing,
            max_add=max(1, min_verified - _count_importable(verified_papers)),
        )
        if extra:
            extra_verified = await verify_recommended_papers(extra)
            supplement_used = True
            verified_papers.extend(extra_verified)

    verified_count = sum(1 for p in verified_papers if p.get("verification_status") == "verified")
    partial_count = sum(1 for p in verified_papers if p.get("verification_status") == "partial")
    unverified_count = sum(1 for p in verified_papers if p.get("verification_status") == "unverified")

    return {
        "discovery_mode": "llm_recommend_web_v3",
        "research_question": rq,
        "research_domain": domain or "未指定",
        "subtopics": rec.get("subtopics") or [],
        "papers": verified_papers,
        "total": len(verified_papers),
        "candidate_count": len(raw_papers),
        "verified_count": verified_count,
        "partial_count": partial_count,
        "unverified_count": unverified_count,
        "rationale": rec.get("rationale") or "",
        "search_queries": rec.get("search_queries") or [],
        "supplement_used": supplement_used,
        "llm_skipped": bool(rec.get("skipped")),
        "warnings": ([rec.get("error")] if rec.get("error") else []),
    }


def run_literature_recommendation_sync(
    research_question: str,
    research_domain: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    return asyncio.run(
        run_literature_recommendation(
            research_question,
            research_domain,
            **kwargs,
        )
    )
