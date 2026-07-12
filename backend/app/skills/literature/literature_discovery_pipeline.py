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

# 泛化检索：停用词过滤（非领域硬编码）
_SEARCH_STOPWORDS = frozenset({
    "the", "and", "for", "with", "how", "what", "whether", "are", "is", "in", "on", "to", "of",
    "a", "an", "or", "not", "can", "does", "do", "be", "by", "from", "this", "that", "which",
    "问题", "如何", "是否", "有没有", "方案", "研究", "应用", "场景", "不同", "存在", "实现",
    "方法", "机制", "设计", "一种", "解决", "从而", "以及", "进行", "关于", "对于", "全局",
    "稳定", "高精度", "预测", "模型", "数据", "设备", "客户端", "空间", "重叠",
})


def normalize_api_search_query(query: str) -> str:
    """将 LLM 布尔检索式转为 API 友好的空格关键词（arXiv/OpenAlex 不支持 AND/OR/括号）。"""
    q = (query or "").strip()
    if not q:
        return ""
    phrases = re.findall(r'"([^"]+)"', q)
    q = re.sub(r"\b(AND|OR|NOT)\b", " ", q, flags=re.I)
    q = re.sub(r'["\(\)]', " ", q)
    tokens: List[str] = []
    for p in phrases:
        p = p.strip()
        if len(p) >= 2:
            tokens.append(p)
    for t in re.split(r"[\s,，；;、/|]+", q):
        t = t.strip()
        if len(t) >= 2 and t.lower() not in ("and", "or", "not"):
            tokens.append(t)
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return " ".join(out[:12])[:240]


def extract_core_concepts(
    research_question: str,
    keywords: Optional[List[str]] = None,
    extra_terms: Optional[List[str]] = None,
) -> List[str]:
    """概念泛化：从问题/关键词提取可迁移的核心术语（跨领域通用，无硬编码领域表）。"""
    raw_parts: List[str] = [research_question or ""]
    raw_parts.extend(str(k) for k in (keywords or []) if k)
    raw_parts.extend(str(t) for t in (extra_terms or []) if t)

    concepts: List[str] = []
    seen: Set[str] = set()

    def _add(c: str) -> None:
        c = c.strip()
        if len(c) < 2:
            return
        key = c.lower()
        if key in _SEARCH_STOPWORDS:
            return
        if key not in seen:
            seen.add(key)
            concepts.append(c)

    for part in raw_parts:
        norm = normalize_api_search_query(str(part)) or str(part)
        for zh in re.findall(r"[\u4e00-\u9fff]{2,12}", norm):
            _add(zh)
        for token in re.split(r"[\s,，。；;、/|]+", norm):
            token = token.strip(".,;:")
            if not token:
                continue
            if re.fullmatch(r"[A-Za-z]{2,}", token):
                _add(token)
            elif len(token) >= 3 and re.search(r"[A-Za-z]", token):
                _add(token)
    return concepts[:24]


def concept_overlap_stats(
    paper: Dict[str, Any],
    core_concepts: List[str],
) -> Tuple[int, float, List[str]]:
    """术语过滤：统计论文与核心概念的重叠（标题权重高于摘要）。"""
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    matched: List[str] = []
    weight = 0.0
    for concept in core_concepts:
        c = concept.lower().strip()
        if len(c) < 2:
            continue
        in_title = c in title or (len(c) >= 4 and c in title.replace("-", " "))
        in_abstract = c in abstract
        if in_title:
            matched.append(concept)
            weight += 2.0
        elif in_abstract:
            matched.append(concept)
            weight += 1.0
    return len(matched), weight, matched


def passes_concept_filter(
    paper: Dict[str, Any],
    core_concepts: List[str],
    *,
    min_matches: Optional[int] = None,
) -> bool:
    """跨领域可迁移：要求论文覆盖足够数量的核心概念，而非维护领域黑名单。"""
    if not core_concepts:
        return True
    count, _, matched = concept_overlap_stats(paper, core_concepts)
    required = min_matches if min_matches is not None else max(2, min(4, len(core_concepts) // 4))
    if len(core_concepts) <= 3:
        required = 1
    if count >= required:
        return True
    title = (paper.get("title") or "").lower()
    if any(len(m) >= 6 and m.lower() in title for m in matched):
        return count >= 1
    return False


def build_generalized_queries(
    research_question: str,
    keywords: Optional[List[str]] = None,
) -> List[str]:
    """用核心概念组合生成可迁移的 API 检索式（与领域无关）。"""
    concepts = extract_core_concepts(research_question, keywords=keywords)
    if not concepts:
        return heuristic_expand_queries(research_question, keywords)

    en = [c for c in concepts if re.search(r"[A-Za-z]", c)]
    zh = [c for c in concepts if re.search(r"[\u4e00-\u9fff]", c)]
    queries: List[str] = []
    if en:
        queries.append(" ".join(en[:6])[:200])
        if len(en) > 3:
            queries.append(" ".join(en[3:9])[:200])
    if zh:
        queries.append(" ".join(zh[:5])[:120])
    merged = heuristic_expand_queries(research_question, keywords)
    seen = {q.lower() for q in queries}
    for q in merged:
        if q.lower() not in seen and len(queries) < MAX_QUERIES:
            queries.append(q)
            seen.add(q.lower())
    return queries[:MAX_QUERIES] or merged


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
        return build_generalized_queries(research_question, keywords)

    kw_hint = ", ".join(keywords or [])[:200]
    prompt = (
        "你是学术文献检索专家。根据研究问题生成 3 条互补的英文学术检索式。\n"
        "要求：每条为 4~8 个英文关键词，用空格分隔；不要使用 AND/OR/NOT、括号或引号。\n"
        "覆盖方法名、应用场景与核心机制，避免重复。\n\n"
        f"研究问题: {research_question}\n"
        f"已知关键词: {kw_hint or '无'}\n"
    )
    schema = {
        "queries": [
            "federated learning IoT heterogeneous labels",
            "vertical federated learning label alignment privacy",
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
        cleaned = [
            normalize_api_search_query(str(q).strip())
            for q in (queries or [])
            if str(q).strip()
        ]
        cleaned = [q for q in cleaned if q]
        if cleaned:
            merged = heuristic_expand_queries(research_question, keywords)
            for q in merged:
                norm = normalize_api_search_query(q)
                if norm and norm not in cleaned and len(cleaned) < MAX_QUERIES:
                    cleaned.append(norm)
            return cleaned[:MAX_QUERIES]
    except Exception as exc:
        logger.warning("LLM 检索词扩展失败，使用启发式: %s", exc)
    return build_generalized_queries(research_question, keywords)


def score_paper_relevance(
    paper: Dict[str, Any],
    research_question: str,
    extra_terms: Optional[List[str]] = None,
    *,
    keywords: Optional[List[str]] = None,
) -> float:
    """Selector 打分 — 词匹配 + 核心概念重叠 + 引用量。"""
    core = extract_core_concepts(research_question, keywords=keywords, extra_terms=extra_terms)
    q = (research_question or "").lower()
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    terms: List[str] = []
    for src in [q] + list(extra_terms or []):
        norm_src = normalize_api_search_query(str(src)) or str(src)
        for t in re.split(r"[\s,，。；;、/|]+", norm_src.lower()):
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

    _, overlap_w, _ = concept_overlap_stats(paper, core)
    score += overlap_w * 0.9

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


def filter_papers_by_llm_relevance(
    papers: List[Dict[str, Any]],
    research_question: str,
    *,
    domain_hint: str = "",
    max_check: int = 12,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """最终 LLM 门控：批量判断候选论文是否与输入问题或其研究领域相关。"""
    from app.core.config import get_settings
    from app.services.qwen_client import qwen_structured_chat

    if not papers:
        return [], {"skipped": True, "reason": "empty_candidates"}

    settings = get_settings()
    if settings.USE_MOCK_LLM or not (settings.QWEN_API_KEY or "").strip():
        return papers, {"skipped": True, "reason": "llm_unavailable"}

    batch = papers[:max_check]
    catalog = [
        {
            "index": i,
            "title": (p.get("title") or "")[:220],
            "abstract": (p.get("abstract") or "")[:450],
        }
        for i, p in enumerate(batch)
    ]
    prompt = (
        "你是学术文献相关性审稿人。请判断每篇候选论文是否与「研究问题」或其学科领域真正相关。\n"
        "规则：\n"
        "- 研究对象、应用场景、方法目标应与问题一致或高度相关；\n"
        "- 仅因泛化词（如 privacy、learning、transfer）部分重叠但领域明显不同的，判为不相关；\n"
        "- 跨学科但直接回答问题的综述/方法论文可判为相关。\n\n"
        f"研究问题:\n{research_question[:700]}\n\n"
        f"领域/关键词提示: {(domain_hint or '无')[:300]}\n\n"
        f"候选论文:\n{json.dumps(catalog, ensure_ascii=False, indent=2)}"
    )
    schema = {
        "reviews": [
            {
                "index": 0,
                "relevant": True,
                "reason": "与问题领域直接相关的一句话理由",
            }
        ],
    }
    meta: Dict[str, Any] = {"checked": len(batch), "kept": len(batch)}
    try:
        result = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema,
            temperature=0.1,
            prompt_version="literature_relevance_gate_v1",
        )
        reviews = result.get("reviews") if isinstance(result, dict) else []
        reject: Set[int] = set()
        review_log: List[Dict[str, Any]] = []
        for row in reviews or []:
            if not isinstance(row, dict):
                continue
            idx = row.get("index")
            if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                continue
            relevant = bool(row.get("relevant"))
            reason = str(row.get("reason") or "")[:200]
            review_log.append({"index": idx, "relevant": relevant, "reason": reason, "title": catalog[idx]["title"][:120]})
            if not relevant:
                reject.add(idx)
        kept = [p for i, p in enumerate(batch) if i not in reject]
        meta = {
            "skipped": False,
            "checked": len(batch),
            "kept": len(kept),
            "rejected": len(reject),
            "reviews": review_log[:20],
        }
        logger.info(
            "[文献相关性门控] checked=%s kept=%s rejected=%s",
            meta["checked"],
            meta["kept"],
            meta["rejected"],
        )
        return kept, meta
    except Exception as exc:
        logger.warning("[文献相关性门控] LLM 失败，保留概念过滤结果: %s", exc)
        return papers, {"skipped": True, "reason": "llm_error", "error": str(exc)[:200]}


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
            api_query = normalize_api_search_query(query) or query
            try:
                result = await self.search_skill.run(
                    input_data={
                        "research_question": api_query,
                        "keywords": keywords or [],
                        "max_results": max(10, max_results // max(1, len(queries))),
                        "sources": self.sources,
                    },
                    context={"stage": "literature_discovery", "query_index": qi},
                )
                papers = (result.data or {}).get("papers") or []
                all_papers.extend(papers)
                per_query_status.append({"query": api_query, "count": len(papers), "success": result.success})
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
                key=lambda p: score_paper_relevance(p, research_question, queries, keywords=keywords),
                reverse=True,
            )
            cite_papers, citation_warnings = await expand_citations_openalex(ranked_seeds)
            if cite_papers:
                merged, _ = self.search_skill._deduplicate_papers(deduped + cite_papers)
                citation_expanded = len(merged) - len(deduped)
                deduped = merged

        ranked = sorted(
            deduped,
            key=lambda p: score_paper_relevance(p, research_question, queries, keywords=keywords),
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
