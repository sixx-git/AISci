"""文献检索结果自动入库 — Search → Import → Parse → Index"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.skills.literature.literature_discovery_pipeline import score_paper_relevance

logger = logging.getLogger(__name__)


def _score_paper_relevance(
    paper: Dict[str, Any],
    query: str,
    extra_terms: Optional[List[str]] = None,
) -> float:
    return score_paper_relevance(paper, query, extra_terms)


def ensure_corpora_from_discovery(
    project_id: str,
    research_question: str,
    discovery_output: Optional[Dict[str, Any]],
    db: Session,
    *,
    max_import: int = 8,
    auto_parse: bool = True,
    min_score: float = 0.8,
) -> Dict[str, Any]:
    """将文献发现流水线（Crawler+Selector）结果自动导入文献库并索引。"""
    queries = (discovery_output or {}).get("queries") or []
    search_like = {
        "papers": (discovery_output or {}).get("papers") or [],
        "sources_searched": (discovery_output or {}).get("sources_searched") or [],
        "queries": queries,
        "discovery_mode": (discovery_output or {}).get("discovery_mode"),
        "citation_expanded": (discovery_output or {}).get("citation_expanded", 0),
    }
    meta = ensure_corpora_from_search(
        project_id,
        research_question,
        search_like,
        db,
        max_import=max_import,
        auto_parse=auto_parse,
        min_score=min_score,
        extra_terms=queries,
    )
    if discovery_output:
        meta["discovery"] = {
            "queries": queries,
            "candidate_count": discovery_output.get("candidate_count"),
            "citation_expanded": discovery_output.get("citation_expanded"),
            "per_query_status": discovery_output.get("per_query_status"),
            "warnings": discovery_output.get("warnings"),
        }
    return meta


def ensure_corpora_from_search(
    project_id: str,
    research_question: str,
    search_papers_output: Optional[Dict[str, Any]],
    db: Session,
    *,
    max_import: int = 8,
    auto_parse: bool = True,
    min_score: float = 0.8,
    extra_terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """将 search_papers 高相关结果自动导入文献库并索引。"""
    from app.models import SourceType
    from app.services.literature_ingestion_service import LiteratureIngestionService
    from app.services.vector_store import build_vector_index

    papers = (search_papers_output or {}).get("papers") or []
    if not papers:
        return {"imported": 0, "skipped": True, "reason": "无 search_papers 结果"}

    terms = list(extra_terms or [])
    if (search_papers_output or {}).get("queries"):
        terms.extend((search_papers_output or {}).get("queries") or [])

    ranked = sorted(
        papers,
        key=lambda p: _score_paper_relevance(p, research_question, terms),
        reverse=True,
    )[: max_import * 3]

    effective_min = min_score
    if len(ranked) < 3:
        effective_min = min(min_score, 0.3)

    to_import: List[Dict[str, Any]] = []
    for p in ranked:
        if len(to_import) >= max_import:
            break
        if _score_paper_relevance(p, research_question, terms) < effective_min:
            continue
        ext_id = p.get("external_id") or p.get("arxiv_id") or p.get("doi") or ""
        if not ext_id and not p.get("title"):
            continue
        item = dict(p)
        if not item.get("external_id"):
            item["external_id"] = ext_id or item.get("title", "")[:40]
        to_import.append(item)

    if not to_import:
        return {"imported": 0, "skipped": True, "reason": "无足够相关论文"}

    service = LiteratureIngestionService(db)
    arxiv_batch = [p for p in to_import if p.get("arxiv_id") or p.get("source") == "arxiv"]
    other_batch = [p for p in to_import if p not in arxiv_batch]

    imported_ids: List[str] = []
    import_results: List[Dict[str, Any]] = []

    if arxiv_batch:
        res = service.import_arxiv_papers(project_id, arxiv_batch, SourceType.ARXIV)
        import_results.extend(res.get("results") or [])
        for r in res.get("results") or []:
            if r.get("document_id") and not r.get("duplicate"):
                imported_ids.append(r["document_id"])

    if other_batch:
        res = service.import_arxiv_papers(project_id, other_batch, SourceType.OPENALEX)
        import_results.extend(res.get("results") or [])
        for r in res.get("results") or []:
            if r.get("document_id") and not r.get("duplicate"):
                imported_ids.append(r["document_id"])

    parsed = 0
    pdf_downloaded = 0
    if auto_parse and imported_ids:
        for doc_id in imported_ids:
            try:
                from app.models import Document

                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc and doc.pdf_url and not doc.file_path:
                    try:
                        service.download_arxiv_pdf(project_id, doc_id)
                        pdf_downloaded += 1
                    except Exception as dl_err:
                        logger.warning("PDF 下载失败 %s: %s", doc_id, dl_err)
                service.parse_document(project_id=project_id, document_id=doc_id)
                parsed += 1
            except Exception as parse_err:
                logger.warning("自动 parse 失败 %s: %s", doc_id, parse_err)
        try:
            build_vector_index(project_id=project_id)
        except Exception as idx_err:
            logger.warning("自动索引失败: %s", idx_err)

    return {
        "imported": len(imported_ids),
        "parsed": parsed,
        "pdf_downloaded": pdf_downloaded,
        "candidate_count": len(papers),
        "selected_count": len(to_import),
        "import_results": import_results[:10],
        "retrieval_provenance": {
            "query": research_question[:200],
            "expanded_queries": terms[:8],
            "source_api": (search_papers_output or {}).get("sources_searched") or [],
            "discovery_mode": (search_papers_output or {}).get("discovery_mode"),
            "imported_ids": imported_ids,
            "auto_parse": auto_parse,
        },
    }
