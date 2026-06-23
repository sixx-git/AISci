"""Data Finder 文献发现适配器 — 按 DataSpec 自动检索并导入 arXiv/OpenAlex 文献"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import SourceType

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAPERS = 5
DEFAULT_MIN_EXISTING_DOCS = 3


def _build_search_query(research_question: str, data_spec: Optional[Dict[str, Any]] = None) -> str:
    parts: List[str] = []
    if research_question and research_question.strip():
        parts.append(research_question.strip()[:300])
    spec = data_spec or {}
    for kw in (spec.get("dataset_keywords") or [])[:4]:
        if kw:
            parts.append(str(kw)[:80])
    for kw in (spec.get("domain_keywords") or [])[:3]:
        if kw and str(kw) not in parts:
            parts.append(str(kw)[:80])
    return " ".join(parts)[:400] or "machine learning dataset"


def should_auto_discover_literature(
    existing_doc_count: int,
    project_config: Optional[Dict[str, Any]] = None,
) -> bool:
    cfg = (project_config or {}).get("data_acquisition") or {}
    if cfg.get("auto_literature_discovery") is False:
        return False
    if cfg.get("auto_literature_discovery") is True:
        return True
    try:
        min_docs = int(cfg.get("auto_literature_min_docs", DEFAULT_MIN_EXISTING_DOCS))
    except (TypeError, ValueError):
        min_docs = DEFAULT_MIN_EXISTING_DOCS
    return existing_doc_count < min_docs


def discover_and_import_literature(
    db: Session,
    project_id: str,
    research_question: str,
    data_spec: Optional[Dict[str, Any]] = None,
    *,
    max_papers: int = DEFAULT_MAX_PAPERS,
    download_pdf: bool = True,
    parse_pdf: bool = True,
) -> Dict[str, Any]:
    """检索 arXiv（含 OpenAlex 降级）并导入 Document，可选下载/解析 PDF。"""
    from app.models import Document
    from app.services.literature_ingestion_service import LiteratureIngestionService

    lit = LiteratureIngestionService(db)
    existing_count = db.query(Document).filter(Document.project_id == project_id).count()
    query = _build_search_query(research_question, data_spec)

    try:
        max_papers = max(1, min(int(max_papers), 10))
    except (TypeError, ValueError):
        max_papers = DEFAULT_MAX_PAPERS

    papers, fallback, warning = lit.search_arxiv(query, max_results=max_papers)
    source_type = SourceType.OPENALEX if fallback else SourceType.ARXIV

    import_result = lit.import_arxiv_papers(
        project_id,
        papers[:max_papers],
        source_type=source_type,
        fallback=fallback,
    )

    downloaded: List[str] = []
    parsed: List[str] = []
    abstract_only: List[str] = []
    errors: List[str] = []

    for item in import_result.get("results") or []:
        if item.get("duplicate") or not item.get("document_id"):
            continue
        doc_id = item["document_id"]
        if download_pdf:
            try:
                lit.download_arxiv_pdf(project_id, doc_id)
                downloaded.append(doc_id)
                if parse_pdf:
                    lit.parse_document(project_id, doc_id)
                    parsed.append(doc_id)
            except Exception as exc:
                errors.append(f"{doc_id}: PDF {exc}")
                try:
                    doc = db.query(Document).filter(Document.id == doc_id).first()
                    if doc and doc.abstract and not doc.raw_text:
                        doc.raw_text = doc.abstract
                        db.commit()
                        abstract_only.append(doc_id)
                except Exception:
                    pass
        else:
            try:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc and doc.abstract and not doc.raw_text:
                    doc.raw_text = doc.abstract
                    db.commit()
                    abstract_only.append(doc_id)
            except Exception as exc:
                errors.append(f"{doc_id}: abstract {exc}")

    return {
        "query": query,
        "fallback_source": "openalex" if fallback else "arxiv",
        "warning": warning,
        "existing_docs_before": existing_count,
        "searched": len(papers),
        "imported": import_result.get("imported", 0),
        "duplicates": import_result.get("duplicates", 0),
        "failed": import_result.get("failed", 0),
        "pdf_downloaded": len(downloaded),
        "pdf_parsed": len(parsed),
        "abstract_text_only": len(abstract_only),
        "literature_imported": [
            {
                "document_id": r.get("document_id"),
                "title": r.get("title"),
                "duplicate": r.get("duplicate"),
                "external_id": r.get("external_id"),
            }
            for r in (import_result.get("results") or [])
        ],
        "errors": errors[:6],
    }
