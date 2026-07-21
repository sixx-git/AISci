"""LLM 推荐论文的 API 校验（DOI / arXiv / 标题）。"""
from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from app.services.literature_search_utils import title_similarity_ratio, titles_match

# 强匹配：直接视为 verified/partial
_TITLE_MATCH_RATIO = 0.40
# 弱匹配：DOI/arXiv 命中但标题略偏，或标题检索结果略偏 → partial（保留摘要入库）
_TITLE_SOFT_RATIO = 0.30
from app.skills.literature.search_papers_skill import SearchPapersSkill

logger = logging.getLogger(__name__)


def _clean_doi(doi: str) -> str:
    d = (doi or "").strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    return d.strip()


def _clean_arxiv_id(arxiv_id: str) -> str:
    aid = (arxiv_id or "").strip()
    aid = re.sub(r"^https?://arxiv\.org/abs/", "", aid, flags=re.I)
    if "v" in aid and re.search(r"v\d+$", aid):
        aid = aid.rsplit("v", 1)[0]
    return aid


async def _lookup_openalex_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    doi = _clean_doi(doi)
    if not doi:
        return None
    url = f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}"
    try:
        data = await SearchPapersSkill._http_get_json(url, source_name="openalex")
        if not data or not data.get("title"):
            return None
        return _openalex_to_paper(data)
    except Exception as exc:
        logger.debug("OpenAlex DOI lookup failed %s: %s", doi, exc)
        return None


async def _lookup_arxiv_by_id(arxiv_id: str) -> Optional[Dict[str, Any]]:
    aid = _clean_arxiv_id(arxiv_id)
    if not aid:
        return None
    encoded = urllib.parse.quote(f"id:{aid}")
    url = (
        f"https://export.arxiv.org/api/query?search_query={encoded}"
        f"&start=0&max_results=1"
    )
    try:
        papers = await SearchPapersSkill()._search_arxiv(aid, 1)
        if papers:
            return papers[0]
    except Exception as exc:
        logger.debug("arXiv lookup failed %s: %s", aid, exc)
    return None


async def _lookup_by_title(title: str, *, first_author: str = "") -> Optional[Dict[str, Any]]:
    query = normalize_title_query(title, first_author)
    if not query:
        return None
    skill = SearchPapersSkill()
    try:
        papers = await skill._search_openalex(query, 5)
        for p in papers:
            if titles_match(title, p.get("title") or ""):
                return p
        if papers:
            return papers[0]
    except Exception as exc:
        logger.debug("OpenAlex title search failed: %s", exc)
    try:
        papers = await skill._search_semantic_scholar(query, 5)
        for p in papers:
            if titles_match(title, p.get("title") or ""):
                return p
    except Exception as exc:
        logger.debug("S2 title search failed: %s", exc)
    return None


def normalize_title_query(title: str, first_author: str = "") -> str:
    parts = [(title or "").strip()[:180]]
    if first_author:
        parts.append(str(first_author).strip()[:40])
    return " ".join(p for p in parts if p)


def _openalex_to_paper(item: dict) -> Dict[str, Any]:
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
    doi = item.get("doi", "") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "")
    return {
        "title": item.get("title", "") or "",
        "authors": authors_list,
        "year": item.get("publication_year"),
        "abstract": abstract,
        "source": "openalex",
        "source_url": f"https://doi.org/{doi}" if doi else "",
        "doi": doi,
        "arxiv_id": "",
        "citation_count": item.get("cited_by_count", 0) or 0,
        "venue": source_info.get("display_name", "") or "",
        "pdf_url": primary_loc.get("pdf_url", "") or "",
        "external_id": openalex_id.split("/")[-1] if openalex_id else "",
        "metadata": {"source_api": "openalex", "openalex_id": openalex_id},
    }


async def verify_recommended_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """校验单篇推荐论文，返回 enriched paper + verification_status。"""
    rec = dict(paper)
    doi = _clean_doi(str(rec.get("doi") or ""))
    arxiv_id = _clean_arxiv_id(str(rec.get("arxiv_id") or ""))
    title = str(rec.get("title") or "").strip()
    authors = rec.get("authors") or []
    first_author = authors[0] if isinstance(authors, list) and authors else str(authors or "")

    resolved: Optional[Dict[str, Any]] = None
    verify_method = ""

    if doi:
        resolved = await _lookup_openalex_by_doi(doi)
        verify_method = "doi"
    if not resolved and arxiv_id:
        resolved = await _lookup_arxiv_by_id(arxiv_id)
        verify_method = "arxiv"
    if not resolved and title:
        resolved = await _lookup_by_title(title, first_author=first_author)
        verify_method = "title"

    if not resolved:
        # 外网未命中：保留 LLM 推荐自身的摘要，便于后续「unverified+摘要」入库
        rec["verification_status"] = "unverified"
        rec["verification_method"] = verify_method or "none"
        if not (rec.get("abstract") or "").strip():
            rec["abstract"] = str(rec.get("abstract") or "")
        return rec

    resolved_title = str(resolved.get("title") or "").strip()
    has_abstract = bool((resolved.get("abstract") or "").strip())
    ratio = title_similarity_ratio(title, resolved_title) if title else 1.0
    title_ok = ratio >= _TITLE_MATCH_RATIO if title else True
    soft_ok = ratio >= _TITLE_SOFT_RATIO if title else True

    # DOI/arXiv 命中但标题完全对不上 → 视为错文，不合并（防串号）
    if not soft_ok and verify_method in ("doi", "arxiv"):
        rec["verification_status"] = "unverified"
        rec["verification_method"] = verify_method
        rec["verification_note"] = (
            f"推荐标题与 API 解析不一致: 推荐={title[:120]} / 解析={resolved_title[:120]}"
        )
        rec["resolved_title"] = resolved_title
        rec["resolved_abstract_preview"] = (resolved.get("abstract") or "")[:200]
        # 不把错文摘要写进推荐条目，避免「错误摘要入库」
        return rec

    # 标题弱匹配：接受为 partial，合并 API 元数据（含摘要）
    if not title_ok and soft_ok:
        status = "partial"
        note = (
            f"标题弱匹配(ratio={ratio:.2f}): 推荐={title[:80]} / 解析={resolved_title[:80]}"
        )
    elif title_ok and has_abstract:
        status = "verified"
        note = ""
    else:
        status = "partial"
        note = ""

    # 标题检索弱到完全不像：不合并错误解析；仅当推荐自身已有摘要时才可 unverified 入库
    if not soft_ok and verify_method == "title":
        rec["verification_status"] = "unverified"
        rec["verification_method"] = verify_method
        rec["verification_note"] = (
            f"推荐标题与 API 解析不一致: 推荐={title[:120]} / 解析={resolved_title[:120]}"
        )
        rec["resolved_title"] = resolved_title
        rec["resolved_abstract_preview"] = (resolved.get("abstract") or "")[:200]
        return rec

    merged = {**resolved}
    for k, v in rec.items():
        if k in ("title", "authors", "year", "doi", "arxiv_id", "abstract", "source_url", "pdf_url", "external_id"):
            continue
        if v is not None and v != "":
            merged[k] = v
    # 摘要优先用 API；若 API 无摘要则保留推荐摘要
    if not (merged.get("abstract") or "").strip() and (rec.get("abstract") or "").strip():
        merged["abstract"] = rec.get("abstract")
    # 显式保留推荐阶段相关性分数（含 0 分）
    for k in ("relevance_score", "recommend_relevance_score", "score_source"):
        if k in rec and rec[k] is not None:
            merged[k] = rec[k]
    merged["title"] = resolved_title or title
    merged["verification_status"] = status
    merged["verification_method"] = verify_method
    if note:
        merged["verification_note"] = note
    merged["relevance_reason"] = rec.get("relevance_reason") or merged.get("relevance_reason") or ""
    merged["challenge_ids"] = rec.get("challenge_ids") or rec.get("dimension_ids") or []
    merged["dimension_ids"] = rec.get("dimension_ids") or rec.get("challenge_ids") or []
    merged["category"] = rec.get("category") or ""
    merged["recommended_title"] = title
    merged["title_match_ratio"] = round(ratio, 3)
    return merged


async def verify_recommended_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not papers:
        return []
    tasks = [verify_recommended_paper(p) for p in papers]
    return list(await asyncio.gather(*tasks))
