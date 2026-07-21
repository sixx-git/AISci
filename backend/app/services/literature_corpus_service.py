"""文献推荐结果自动入库 — Recommend → Verify → Import → Index"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _literature_import_settings() -> tuple[int, bool, bool, bool]:
    from app.core.config import get_settings

    s = get_settings()
    return (
        int(getattr(s, "LITERATURE_RECOMMEND_MAX", 12) or getattr(s, "LITERATURE_IMPORT_MAX", 12) or 12),
        bool(getattr(s, "LITERATURE_IMPORT_UNVERIFIED", False)),
        bool(getattr(s, "LITERATURE_IMPORT_UNVERIFIED_WITH_ABSTRACT", True)),
        bool(getattr(s, "LITERATURE_DISCOVERY_DOWNLOAD_PDF", False)),
    )


def _paper_abstract(paper: Dict[str, Any]) -> str:
    return str(
        paper.get("abstract")
        or paper.get("resolved_abstract_preview")
        or ""
    ).strip()


def _importable_papers(
    papers: List[Dict[str, Any]],
    *,
    import_unverified: bool,
    import_unverified_with_abstract: bool = True,
    min_abstract_chars: int = 40,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in papers:
        status = p.get("verification_status") or ""
        abstract = _paper_abstract(p)
        if status in ("verified", "partial"):
            out.append(p)
        elif status == "unverified" and p.get("title"):
            if import_unverified:
                out.append(p)
            elif import_unverified_with_abstract and len(abstract) >= min_abstract_chars:
                # 带摘要的 unverified：允许入库（用于摘要级证据与引用）
                enriched = dict(p)
                if not (enriched.get("abstract") or "").strip():
                    enriched["abstract"] = abstract
                enriched["import_via"] = "unverified_with_abstract"
                out.append(enriched)
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
    from app.services.literature_relevance_gate import apply_relevance_gate
    from app.services.vector_store import build_vector_index

    default_max, import_unverified, import_unverified_with_abstract, download_pdf = (
        _literature_import_settings()
    )
    max_import = max_import if max_import is not None else default_max

    # 入库前论文级相关性门控 + 查询改写（可配置关闭）
    gated = apply_relevance_gate(
        research_question,
        recommendation_output,
        research_domain=str((recommendation_output or {}).get("research_domain") or ""),
    )
    if recommendation_output is not None and isinstance(recommendation_output, dict):
        recommendation_output.clear()
        recommendation_output.update(gated)

    papers = gated.get("papers") or []
    gate_stats = gated.get("gate_stats") or {}
    if not papers:
        return {
            "imported": 0,
            "skipped": True,
            "reason": (
                "相关性门控后无通过论文"
                if gate_stats.get("enabled") and gate_stats.get("candidate_count")
                else "无推荐论文"
            ),
            "candidate_count": int(gate_stats.get("candidate_count") or 0),
            "gate_stats": gate_stats,
        }

    to_import = _importable_papers(
        papers,
        import_unverified=import_unverified,
        import_unverified_with_abstract=import_unverified_with_abstract,
    )[:max_import]
    if not to_import:
        return {
            "imported": 0,
            "skipped": True,
            "reason": "无通过校验的论文可入库（且无可带摘要的 unverified 候选）",
            "candidate_count": len(papers),
            "verified_count": gated.get("verified_count", 0),
            "unverified_count": gated.get("unverified_count", 0),
            "gate_stats": gate_stats,
        }

    service = LiteratureIngestionService(db)
    imported_ids, import_results = _import_paper_batches(service, project_id, to_import)

    parsed = 0
    pdf_downloaded = 0
    abstract_indexed = 0
    if auto_parse and imported_ids:
        for doc_id in imported_ids:
            try:
                from app.models import Document

                doc = db.query(Document).filter(Document.id == doc_id).first()
                abstract = (doc.abstract or "").strip() if doc else ""
                has_usable_abstract = len(abstract) >= 40

                # 默认不下载 PDF：有摘要则直接建摘要索引，避免串行 60s 超时拖垮 discovery
                should_download = (
                    download_pdf
                    and doc
                    and doc.pdf_url
                    and not doc.file_path
                    and not has_usable_abstract
                )
                if should_download:
                    try:
                        service.download_arxiv_pdf(project_id, doc_id)
                        pdf_downloaded += 1
                    except Exception as dl_err:
                        logger.warning("PDF 下载失败 %s: %s", doc_id, dl_err)
                elif doc and doc.pdf_url and not download_pdf:
                    logger.info(
                        "跳过 PDF 下载（LITERATURE_DISCOVERY_DOWNLOAD_PDF=false）doc=%s",
                        doc_id,
                    )

                indexed_ok = False
                if has_usable_abstract and not (doc and doc.file_path):
                    try:
                        if service.ensure_abstract_chunks(project_id, doc_id):
                            abstract_indexed += 1
                            indexed_ok = True
                    except Exception as abs_err:
                        logger.warning("摘要 chunk 写入失败 %s: %s", doc_id, abs_err)

                if not indexed_ok and doc and doc.file_path:
                    try:
                        service.parse_document(project_id=project_id, document_id=doc_id)
                        parsed += 1
                        indexed_ok = True
                    except Exception as parse_err:
                        logger.warning("自动 parse 失败 %s: %s", doc_id, parse_err)

                if not indexed_ok:
                    try:
                        if service.ensure_abstract_chunks(project_id, doc_id):
                            abstract_indexed += 1
                    except Exception as abs_err:
                        logger.warning("摘要 chunk 回退失败 %s: %s", doc_id, abs_err)
            except Exception as parse_err:
                logger.warning("自动 parse 失败 %s: %s", doc_id, parse_err)
        try:
            build_vector_index(project_id=project_id)
        except Exception as idx_err:
            logger.warning("自动索引失败: %s", idx_err)

    rec = gated
    pre_gate = int(gate_stats.get("candidate_count") or len(papers))
    return {
        "imported": len(imported_ids),
        "parsed": parsed,
        "pdf_downloaded": pdf_downloaded,
        "abstract_indexed": abstract_indexed,
        "candidate_count": pre_gate,
        "selected_count": len(to_import),
        "import_results": import_results[:10],
        "verified_count": rec.get("verified_count", 0),
        "partial_count": rec.get("partial_count", 0),
        "unverified_count": rec.get("unverified_count", 0),
        "gate_stats": gate_stats,
        "download_pdf": download_pdf,
        "retrieval_provenance": {
            "query": research_question[:200],
            "research_domain": rec.get("research_domain") or "",
            "discovery_mode": rec.get("discovery_mode", "llm_recommend_web_v3"),
            "subtopics": rec.get("subtopics") or [],
            "rationale": (rec.get("rationale") or "")[:500],
            "search_queries": rec.get("search_queries") or [],
            "rewritten_queries": rec.get("rewritten_queries") or [],
            "supplement_used": rec.get("supplement_used", False),
            "imported_ids": imported_ids,
            "auto_parse": auto_parse,
            "download_pdf": download_pdf,
            "gate_stats": gate_stats,
            "abstract_indexed": abstract_indexed,
        },
        "discovery": {
            "subtopics": rec.get("subtopics") or [],
            "verified_count": rec.get("verified_count"),
            "unverified_count": rec.get("unverified_count"),
            "supplement_used": rec.get("supplement_used"),
            "search_queries": rec.get("search_queries") or [],
            "warnings": rec.get("warnings"),
            "gate_stats": gate_stats,
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
