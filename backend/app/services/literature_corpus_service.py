"""文献推荐结果自动入库 — Recommend → Verify → Import → Index"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _literature_import_settings() -> tuple[int, bool]:
    from app.core.config import get_settings

    s = get_settings()
    return (
        int(getattr(s, "LITERATURE_RECOMMEND_MAX", 12) or getattr(s, "LITERATURE_IMPORT_MAX", 12) or 12),
        bool(getattr(s, "LITERATURE_IMPORT_UNVERIFIED", False)),
    )


def _importable_papers(
    papers: List[Dict[str, Any]],
    *,
    import_unverified: bool,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in papers:
        status = p.get("verification_status") or ""
        if status in ("verified", "partial"):
            out.append(p)
        elif import_unverified and status == "unverified" and p.get("title"):
            out.append(p)
    return out


def _import_paper_batches(
    service: Any,
    project_id: str,
    to_import: List[Dict[str, Any]],
) -> tuple[List[str], List[Dict[str, Any]]]:
    from app.models import SourceType

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

    return imported_ids, import_results


def ensure_corpora_from_recommendations(
    project_id: str,
    research_question: str,
    recommendation_output: Optional[Dict[str, Any]],
    db: Session,
    *,
    max_import: Optional[int] = None,
    auto_parse: bool = True,
) -> Dict[str, Any]:
    """将 LLM 推荐 + API 校验后的论文导入文献库并索引。"""
    from app.services.literature_ingestion_service import LiteratureIngestionService
    from app.services.vector_store import build_vector_index

    default_max, import_unverified = _literature_import_settings()
    max_import = max_import if max_import is not None else default_max

    papers = (recommendation_output or {}).get("papers") or []
    if not papers:
        return {
            "imported": 0,
            "skipped": True,
            "reason": "无推荐论文",
            "candidate_count": 0,
        }

    to_import = _importable_papers(papers, import_unverified=import_unverified)[:max_import]
    if not to_import:
        return {
            "imported": 0,
            "skipped": True,
            "reason": "无通过校验的论文可入库",
            "candidate_count": len(papers),
            "verified_count": (recommendation_output or {}).get("verified_count", 0),
            "unverified_count": (recommendation_output or {}).get("unverified_count", 0),
        }

    service = LiteratureIngestionService(db)
    imported_ids, import_results = _import_paper_batches(service, project_id, to_import)

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

    rec = recommendation_output or {}
    return {
        "imported": len(imported_ids),
        "parsed": parsed,
        "pdf_downloaded": pdf_downloaded,
        "candidate_count": len(papers),
        "selected_count": len(to_import),
        "import_results": import_results[:10],
        "verified_count": rec.get("verified_count", 0),
        "partial_count": rec.get("partial_count", 0),
        "unverified_count": rec.get("unverified_count", 0),
        "retrieval_provenance": {
            "query": research_question[:200],
            "research_domain": rec.get("research_domain") or "",
            "discovery_mode": rec.get("discovery_mode", "llm_recommend_web_v3"),
            "subtopics": rec.get("subtopics") or [],
            "rationale": (rec.get("rationale") or "")[:500],
            "search_queries": rec.get("search_queries") or [],
            "supplement_used": rec.get("supplement_used", False),
            "imported_ids": imported_ids,
            "auto_parse": auto_parse,
        },
        "discovery": {
            "subtopics": rec.get("subtopics") or [],
            "verified_count": rec.get("verified_count"),
            "unverified_count": rec.get("unverified_count"),
            "supplement_used": rec.get("supplement_used"),
            "search_queries": rec.get("search_queries") or [],
            "warnings": rec.get("warnings"),
        },
    }


def ensure_corpora_from_search(
    project_id: str,
    research_question: str,
    search_papers_output: Optional[Dict[str, Any]],
    db: Session,
    *,
    max_import: Optional[int] = None,
    auto_parse: bool = True,
    **_: Any,
) -> Dict[str, Any]:
    """兼容旧调用：将 search_papers 结果按 verified 逻辑入库（Data Finder 等）。"""
    papers = (search_papers_output or {}).get("papers") or []
    for p in papers:
        if not p.get("verification_status"):
            p["verification_status"] = "verified" if (p.get("abstract") or "").strip() else "partial"
    fake_rec = {
        "papers": papers,
        "discovery_mode": (search_papers_output or {}).get("discovery_mode") or "search_papers",
        "verified_count": len(papers),
    }
    return ensure_corpora_from_recommendations(
        project_id,
        research_question,
        fake_rec,
        db,
        max_import=max_import,
        auto_parse=auto_parse,
    )
