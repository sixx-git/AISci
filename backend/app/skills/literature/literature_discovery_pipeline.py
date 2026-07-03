"""
文献发现流水线 — 参考 PaSa / PaperSeek / ScholarClaw / Feynman 成熟模式

阶段:
  1. Query Expander  — 自然语言问题 → 多条互补检索式
  2. Multi-source Search — arXiv / Semantic Scholar / OpenAlex / Crossref
  3. Citation Crawler — 从高相关种子论文沿 OpenAlex 引用网络扩展
  4. Selector — 相关性打分 + 去重，输出候选论文列表
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

from app.skills.literature.search_papers_skill import SearchPapersSkill

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
DEFAULT_SOURCES = ["openalex", "semantic_scholar", "arxiv"]
MAX_QUERIES = 3
INTER_QUERY_DELAY_SEC = 4.0
MAX_CITATION_SEEDS = 2
MAX_CITATION_PER_SEED = 5


def _tokenize_query(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"[\s,，。；;、/|]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 2][:12]


def heuristic_expand_queries(research_question: str, keywords: Optional[List[str]] = None) -> List[str]:
    """无 LLM 时的检索词扩展（PaperSeek 式多 query）。"""
    base = (research_question or "").strip()
    kws = [k.strip() for k in (keywords or []) if isinstance(k, str) and k.strip()]
    queries: List[str] = []

    if base:
        queries.append(base[:280])
    if kws:
        queries.append(" ".join(kws[:6])[:200])
        if len(kws) >= 2:
            queries.append(" ".join(kws[:3])[:160])
            queries.append(" ".join(kws[-3:])[:160])

    tokens = _tokenize_query(base)
    en_tokens = [t for t in tokens if re.search(r"[A-Za-z]", t)]
    zh_tokens = [t for t in tokens if re.search(r"[\u4e00-\u9fff]", t)]
    if en_tokens:
        queries.append(" ".join(en_tokens[:6])[:200])
    if zh_tokens and len(zh_tokens) >= 2:
        queries.append(" ".join(zh_tokens[:4])[:120])

    # 去重保序
    seen: Set[str] = set()
    out: List[str] = []
    for q in queries:
        key = q.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(q)
    return out[:MAX_QUERIES] or ([base] if base else [])


def expand_queries_llm(research_question: str, keywords: Optional[List[str]] = None) -> List[str]:
    """LLM 扩展检索词（PaSa Crawler 式 query generation）。"""
    from app.core.config import get_settings
    from app.services.qwen_client import qwen_structured_chat

    settings = get_settings()
    if settings.USE_MOCK_LLM or not settings.QWEN_API_KEY:
        return heuristic_expand_queries(research_question, keywords)

    kw_hint = ", ".join(keywords or [])[:200]
    prompt = (
        "你是学术文献检索专家。根据研究问题生成 3~5 条互补的英文学术检索式，"
        "覆盖同义词、方法名、应用领域与相关子问题。避免重复。\n\n"
        f"研究问题: {research_question}\n"
        f"已知关键词: {kw_hint or '无'}\n"
    )
    schema = {
        "queries": [
            "query 1 focused on core mechanism",
            "query 2 focused on methods",
        ],
        "rationale": "brief explanation",
    }
    try:
        result = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            temperature=0.3,
            prompt_version="literature_query_expand_v1",
        )
        queries = result.get("queries") if isinstance(result, dict) else []
        cleaned = [str(q).strip() for q in (queries or []) if str(q).strip()]
        if cleaned:
            merged = heuristic_expand_queries(research_question, keywords)
            for q in merged:
                if q not in cleaned and len(cleaned) < MAX_QUERIES:
                    cleaned.append(q)
            return cleaned[:MAX_QUERIES]
    except Exception as exc:
        logger.warning("LLM 检索词扩展失败，使用启发式: %s", exc)
    return heuristic_expand_queries(research_question, keywords)


def score_paper_relevance(paper: Dict[str, Any], research_question: str, extra_terms: Optional[List[str]] = None) -> float:
    """Selector 打分 — 标题/摘要词匹配 + 引用量（PaperSeek/Feynman 式）。"""
    q = (research_question or "").lower()
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    terms: List[str] = []
    for src in [q] + [t.lower() for t in (extra_terms or [])]:
        for t in re.split(r"[\s,，。；;、/|]+", src):
            t = t.strip()
            if len(t) >= 2:
                terms.append(t)
    seen: Set[str] = set()
    unique_terms = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique_terms.append(t)

    score = 0.0
    for term in unique_terms[:20]:
        if term in title:
            score += 2.5
        elif len(term) >= 4 and term in abstract:
            score += 0.8
        elif len(term) >= 3 and any(term in w for w in title.split()):
            score += 1.2

    if paper.get("arxiv_id") or paper.get("pdf_url"):
        score += 0.5
    try:
        cites = float(paper.get("citation_count") or 0)
        score += min(2.0, cites / 80.0)
    except (TypeError, ValueError):
        pass
    if paper.get("selector_relevant") is True:
        score += 3.0
    if paper.get("selector_relevant") is False:
        score -= 5.0
    return score


async def _http_get_json(url: str, *, source_name: str = "openalex") -> dict:
    from app.skills.literature.search_papers_skill import SearchPapersSkill
    return await SearchPapersSkill._http_get_json(url, source_name=source_name)


def _openalex_work_id(paper: Dict[str, Any]) -> Optional[str]:
    meta = paper.get("metadata") or {}
    oid = meta.get("openalex_id") or paper.get("openalex_id") or ""
    if oid:
        return oid.split("/")[-1] if "/" in oid else oid
    ext = paper.get("external_id") or ""
    if ext and ext.startswith("W"):
        return ext
    doi = (paper.get("doi") or "").strip()
    if doi:
        return None  # resolved below via search
    return None


async def expand_citations_openalex(
    seed_papers: List[Dict[str, Any]],
    *,
    max_per_seed: int = MAX_CITATION_PER_SEED,
    max_total: int = 20,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """PaSa 式引用网络扩展 — 从种子论文抓取参考文献与被引论文。"""
    expanded: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for seed in seed_papers[:MAX_CITATION_SEEDS]:
        work_id = _openalex_work_id(seed)
        if not work_id:
            doi = (seed.get("doi") or "").replace("https://doi.org/", "").strip()
            if doi:
                try:
                    data = await _http_get_json(
                        f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}"
                    )
                    work_id = (data.get("id") or "").split("/")[-1]
                except Exception:
                    continue
            else:
                continue

        for relation, label in (
            (f"filter=referenced_works:{work_id}", "references"),
            (f"filter=cites:{work_id}", "cited_by"),
        ):
            try:
                url = (
                    f"https://api.openalex.org/works?{relation}"
                    f"&per_page={max_per_seed}&sort=cited_by_count:desc"
                )
                data = await _http_get_json(url)
                for item in data.get("results") or []:
                    paper = _openalex_item_to_paper(item)
                    paper["metadata"] = {
                        **(paper.get("metadata") or {}),
                        "citation_expand": label,
                        "seed_title": (seed.get("title") or "")[:80],
                    }
                    expanded.append(paper)
            except Exception as exc:
                warnings.append(f"OpenAlex {label} 扩展失败({work_id}): {str(exc)[:80]}")

    # 去重
    skill = SearchPapersSkill()
    deduped, _ = skill._deduplicate_papers(expanded)
    return deduped[:max_total], warnings


def _openalex_item_to_paper(item: dict) -> Dict[str, Any]:
    authors_list = []
    for a in item.get("authorships", []):
        author_obj = (a.get("author") or {})
        authors_list.append(author_obj.get("display_name", ""))
    primary_loc = item.get("primary_location", {}) or {}
    source_info = (primary_loc.get("source") or {}) or {}
    openalex_id = item.get("id", "") or ""
    abstract = ""
    if item.get("abstract_inverted_index"):
        abstract = SearchPapersSkill._reconstruct_openalex_abstract(item["abstract_inverted_index"])
    return {
        "title": item.get("title", "") or "",
        "authors": authors_list,
        "year": item.get("publication_year"),
        "abstract": abstract,
        "source": "openalex",
        "source_url": item.get("doi") and f"https://doi.org/{item['doi']}" or "",
        "doi": item.get("doi", "") or "",
        "arxiv_id": "",
        "citation_count": item.get("cited_by_count", 0) or 0,
        "venue": source_info.get("display_name", "") or "",
        "pdf_url": primary_loc.get("pdf_url", "") or "",
        "external_id": openalex_id.split("/")[-1] if openalex_id else "",
        "metadata": {"source_api": "openalex", "openalex_id": openalex_id},
    }


class LiteratureDiscoveryPipeline:
    """Crawler + Selector 文献发现流水线。"""

    def __init__(self, sources: Optional[List[str]] = None):
        self.sources = sources or list(DEFAULT_SOURCES)
        self.search_skill = SearchPapersSkill()

    async def run(
        self,
        research_question: str,
        *,
        keywords: Optional[List[str]] = None,
        max_results: int = 30,
        expand_citations: bool = True,
        use_llm_expand: bool = True,
    ) -> Dict[str, Any]:
        queries = (
            expand_queries_llm(research_question, keywords)
            if use_llm_expand
            else heuristic_expand_queries(research_question, keywords)
        )
        logger.info("[文献发现] 扩展检索词 %d 条: %s", len(queries), queries)

        all_papers: List[dict] = []
        source_warnings: List[str] = []
        per_query_status: List[Dict[str, Any]] = []

        for qi, query in enumerate(queries):
            if qi > 0:
                await asyncio.sleep(INTER_QUERY_DELAY_SEC)
            try:
                result = await self.search_skill.run(
                    input_data={
                        "research_question": query,
                        "keywords": keywords or [],
                        "max_results": max(10, max_results // max(1, len(queries))),
                        "sources": self.sources,
                    },
                    context={"stage": "literature_discovery", "query_index": qi},
                )
                papers = (result.data or {}).get("papers") or []
                all_papers.extend(papers)
                per_query_status.append({"query": query, "count": len(papers), "success": result.success})
                source_warnings.extend((result.data or {}).get("warnings") or [])
            except Exception as exc:
                per_query_status.append({"query": query, "count": 0, "success": False, "error": str(exc)[:120]})
                source_warnings.append(f"query[{qi}] 失败: {exc}")

        deduped, dedup_count = self.search_skill._deduplicate_papers(all_papers)
        citation_expanded = 0
        citation_warnings: List[str] = []

        if expand_citations and deduped:
            ranked_seeds = sorted(
                deduped,
                key=lambda p: score_paper_relevance(p, research_question, queries),
                reverse=True,
            )
            cite_papers, citation_warnings = await expand_citations_openalex(ranked_seeds)
            if cite_papers:
                merged, _ = self.search_skill._deduplicate_papers(deduped + cite_papers)
                citation_expanded = len(merged) - len(deduped)
                deduped = merged

        ranked = sorted(
            deduped,
            key=lambda p: score_paper_relevance(p, research_question, queries),
            reverse=True,
        )[:max_results]

        return {
            "papers": ranked,
            "total": len(ranked),
            "candidate_count": len(deduped),
            "queries": queries,
            "per_query_status": per_query_status,
            "dedup_count": dedup_count,
            "citation_expanded": citation_expanded,
            "sources_searched": self.sources,
            "warnings": list(dict.fromkeys(source_warnings + citation_warnings)),
            "discovery_mode": "crawler_selector_v1",
        }


def run_literature_discovery_sync(
    research_question: str,
    *,
    keywords: Optional[List[str]] = None,
    max_results: int = 30,
    expand_citations: bool = True,
    use_llm_expand: bool = True,
) -> Dict[str, Any]:
    pipeline = LiteratureDiscoveryPipeline()
    return asyncio.run(
        pipeline.run(
            research_question,
            keywords=keywords,
            max_results=max_results,
            expand_citations=expand_citations,
            use_llm_expand=use_llm_expand,
        )
    )
