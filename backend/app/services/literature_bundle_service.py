"""文献挖掘结果归并：将 facts / citation_map / skill 输出统一为下游可消费结构。"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _abstract_fact_cutoff() -> Optional[float]:
    """门控开启时返回摘要→fact 所需最低 relevance_score（0–10）；关闭则 None（保持旧行为）。"""
    try:
        from app.core.config import get_settings

        s = get_settings()
        if not bool(getattr(s, "LIT_RELEVANCE_GATE_ENABLED", True)):
            return None
        return float(getattr(s, "LIT_PAPER_SCORE_CUTOFF", 6) or 6)
    except Exception:
        return 6.0


def _can_promote_abstract_to_fact(item: Dict[str, Any]) -> bool:
    """摘要兜底进 facts 的门槛：须显式通过门控或分数达标。"""
    cutoff = _abstract_fact_cutoff()
    if cutoff is None:
        return True
    if item.get("gate_passed") is True:
        return True
    if item.get("gate_passed") is False:
        return False
    score = item.get("relevance_score")
    if score is None:
        # 未打分的摘要不得直接变 fact（避免无关 retrieved_papers 污染）
        return False
    try:
        return float(score) >= cutoff
    except (TypeError, ValueError):
        return False


# 辅助白名单来源：权限受限/无 PDF/摘要兜底等，可被假设引用，计入 evidence_facts
_AUXILIARY_SOURCES = frozenset(
    {
        "vector_chunk",
        "chunk",
        "abstract_fallback",
        "retrieved_paper",
        "source_paper",
        "project_library",
        "project_library_chunk",
        "citation_map",
        "literature_evidence",
        "literature_discovery",
        "rcs_rejected_chunk",
    }
)


def classify_fact_tier(fact: Dict[str, Any]) -> str:
    """core = 全文/RCS 通过的 LLM 抽取；auxiliary = 摘要/无 PDF/兜底片段。"""
    explicit = str(fact.get("tier") or "").strip().lower()
    if explicit in ("core", "auxiliary"):
        return explicit
    if fact.get("no_pdf") is True:
        return "auxiliary"
    source = str(fact.get("source") or "").strip().lower()
    if source in _AUXILIARY_SOURCES or "abstract" in source:
        return "auxiliary"
    evidence_level = str(fact.get("evidence_level") or "").strip().lower()
    if evidence_level in ("abstract", "summary", "metadata"):
        return "auxiliary"
    return "core"


def annotate_fact_tiers(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in facts or []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["tier"] = classify_fact_tier(item)
        out.append(item)
    return out


def sync_fact_counts(lm: Dict[str, Any]) -> Dict[str, Any]:
    """写回 evidence_facts / core_facts_count / auxiliary_facts_count（总数含辅助）。"""
    facts = annotate_fact_tiers(_as_dict_list(lm.get("facts")))
    lm["facts"] = facts
    core = sum(1 for f in facts if f.get("tier") != "auxiliary")
    aux = sum(1 for f in facts if f.get("tier") == "auxiliary")
    lm["evidence_facts"] = len(facts)
    lm["core_facts_count"] = core
    lm["auxiliary_facts_count"] = aux
    return lm


def _resolve_abstract_chunk_id(item: Dict[str, Any], *, index: int, prefix: str) -> Tuple[str, bool]:
    """返回 (chunk_id, used_synthetic)。无真实 chunk 时用稳定合成 id，标 no_pdf 辅助事实。"""
    real = str(item.get("source_chunk_id") or item.get("chunk_id") or "").strip()
    if real and not real.startswith(("paper_", "source_paper_", "citation_", "synthetic_")):
        return real, False
    chunk_ids = item.get("chunk_ids") or []
    if isinstance(chunk_ids, list):
        for cid in chunk_ids:
            c = str(cid or "").strip()
            if c and not c.startswith(("paper_", "source_paper_", "citation_", "synthetic_")):
                return c, False
    doc = str(item.get("document_id") or item.get("paper_id") or item.get("external_id") or "").strip()
    if doc:
        return f"{prefix}_{doc}", True
    return f"{prefix}_{index + 1}", True


def _as_dict_list(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            out.append(dict(item))
        elif hasattr(item, "model_dump"):
            out.append(item.model_dump())
    return out


def ensure_citation_document_id(entry: Dict[str, Any], *, index: int = 0) -> Dict[str, Any]:
    """保证 citation 条目有 document_id（LiteratureMiningResponse 必填）。

    外部推荐 / 仅标题的 source_papers 常无库内 doc id，用稳定合成 id 占位。
    """
    item = dict(entry or {})
    doc_id = str(
        item.get("document_id")
        or item.get("paper_id")
        or item.get("external_id")
        or ""
    ).strip()
    if doc_id:
        item["document_id"] = doc_id
        return item
    title = (item.get("title") or item.get("paper_title") or "").strip()
    if title:
        slug = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
        item["document_id"] = f"ext_cite_{slug}"
    else:
        item["document_id"] = f"ext_cite_{index}"
    return item


def _append_fact(
    facts: List[Dict[str, Any]],
    seen_fact_ids: set[str],
    seen_chunks: set[str],
    fact: Dict[str, Any],
) -> None:
    content = (fact.get("content") or fact.get("fact_text") or fact.get("fact") or "").strip()
    if not content:
        return
    fid = str(fact.get("fact_id") or "").strip()
    cid = str(fact.get("source_chunk_id") or fact.get("chunk_id") or "").strip()
    if fid and fid in seen_fact_ids:
        return
    if cid and cid in seen_chunks:
        return
    if not fact.get("content"):
        fact["content"] = content
    if not fact.get("fact_text"):
        fact["fact_text"] = content
    if not fid:
        fid = f"fact_{len(facts) + 1:03d}"
        fact["fact_id"] = fid
    if not cid:
        cid = f"synthetic_{fid}"
        fact["source_chunk_id"] = cid
    facts.append(fact)
    seen_fact_ids.add(fid)
    if cid:
        seen_chunks.add(cid)


def _append_citation(
    citation_map: List[Dict[str, Any]],
    entry: Dict[str, Any],
) -> None:
    title = (entry.get("title") or entry.get("paper_title") or "").strip()
    if not title:
        return
    title_l = title.lower()
    if any(
        (c.get("title") or c.get("paper_title") or "").strip().lower() == title_l
        for c in citation_map
    ):
        return
    citation_map.append(ensure_citation_document_id(entry, index=len(citation_map)))


def normalize_literature_bundle(
    literature_mining: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """将文献挖掘阶段结果规范为 facts / citation_map / verified_references。"""
    lm = literature_mining or {}
    facts = _as_dict_list(lm.get("facts"))
    citation_map = _as_dict_list(lm.get("citation_map"))
    verified = _as_dict_list(lm.get("verified_references"))

    seen_fact_ids = {str(f.get("fact_id")) for f in facts if f.get("fact_id")}
    seen_chunks = {
        str(f.get("source_chunk_id") or f.get("chunk_id"))
        for f in facts
        if f.get("source_chunk_id") or f.get("chunk_id")
    }

    # PdfEvidenceExtractionSkill / 其他 skill 产出
    skill_outputs = lm.get("skill_outputs") or {}
    pdf_data = ((skill_outputs.get("pdf_evidence_extraction") or {}).get("data") or {})
    for i, raw in enumerate(pdf_data.get("facts") or []):
        if not isinstance(raw, dict):
            continue
        _append_fact(
            facts,
            seen_fact_ids,
            seen_chunks,
            {
                "fact_id": raw.get("fact_id") or f"pdf_fact_{i + 1:03d}",
                "content": (raw.get("content") or "")[:600],
                "fact_text": (raw.get("content") or "")[:1200],
                "source_chunk_id": raw.get("source_chunk_id") or raw.get("chunk_id"),
                "document_id": raw.get("document_id"),
                "source_paper_title": raw.get("source_paper_title") or raw.get("source_title"),
                "page_number": raw.get("page_number"),
                "quote_text": (raw.get("quote_text") or raw.get("content") or "")[:300],
                "relevance_score": raw.get("relevance_score"),
                "source": "pdf_evidence_extraction",
            },
        )

    # LLM evidence 列表（与 facts 互补）
    for i, ev in enumerate(lm.get("evidence") or []):
        if not isinstance(ev, dict):
            continue
        text = (ev.get("text") or ev.get("claim") or "").strip()
        if not text:
            continue
        _append_fact(
            facts,
            seen_fact_ids,
            seen_chunks,
            {
                "fact_id": ev.get("fact_id") or ev.get("evidence_id") or f"evidence_fact_{i + 1:03d}",
                "content": text[:600],
                "fact_text": text[:1200],
                "source_chunk_id": ev.get("source_chunk_id"),
                "document_id": ev.get("document_id"),
                "quote_text": text[:300],
                "source": "literature_evidence",
            },
        )

    # 外部检索论文（含摘要）
    for i, paper in enumerate(lm.get("retrieved_papers") or []):
        if not isinstance(paper, dict):
            continue
        title = (paper.get("title") or "").strip()
        if not title:
            continue
        authors = paper.get("authors") or []
        if isinstance(authors, list):
            authors_str = ", ".join(str(a) for a in authors if a)
        else:
            authors_str = str(authors or "")
        entry = {
            "title": title,
            "paper_title": title,
            "authors": authors_str,
            "year": paper.get("year"),
            "abstract": paper.get("abstract"),
            "source_url": paper.get("source_url") or paper.get("url"),
            "doi": paper.get("doi"),
            "external_id": paper.get("arxiv_id") or paper.get("external_id"),
            "source": paper.get("source") or "literature_discovery",
        }
        _append_citation(citation_map, entry)

        abstract = (paper.get("abstract") or "").strip()
        if abstract and _can_promote_abstract_to_fact(paper):
            chunk_id, synthetic = _resolve_abstract_chunk_id(paper, index=i, prefix="abstract_paper")
            _append_fact(
                facts,
                seen_fact_ids,
                seen_chunks,
                {
                    "fact_id": f"paper_fact_{i + 1:03d}",
                    "content": abstract[:600],
                    "fact_text": abstract[:1200],
                    "source_chunk_id": chunk_id,
                    "source_paper_title": title,
                    "quote_text": abstract[:240],
                    "confidence": 0.75,
                    "relevance_score": paper.get("relevance_score"),
                    "source": paper.get("source") or "retrieved_paper",
                    "document_id": paper.get("document_id") or paper.get("paper_id"),
                    "year": paper.get("year"),
                    "doi": paper.get("doi"),
                    "tier": "auxiliary",
                    "no_pdf": True if synthetic or paper.get("no_pdf") else bool(paper.get("no_pdf")),
                    "evidence_level": "abstract",
                },
            )

    # source_papers：可能是标题字符串或元数据 dict
    for i, paper in enumerate(lm.get("source_papers") or []):
        if isinstance(paper, str):
            title = paper.strip()
            if not title:
                continue
            _append_citation(
                citation_map,
                {"title": title, "paper_title": title, "source": "literature_mining"},
            )
            continue
        if not isinstance(paper, dict):
            continue
        title = (paper.get("title") or paper.get("paper_title") or "").strip()
        if not title:
            continue
        _append_citation(citation_map, paper)
        abstract = (paper.get("abstract") or "").strip()
        if abstract and _can_promote_abstract_to_fact(paper):
            chunk_id, synthetic = _resolve_abstract_chunk_id(paper, index=i, prefix="abstract_source")
            _append_fact(
                facts,
                seen_fact_ids,
                seen_chunks,
                {
                    "fact_id": paper.get("fact_id") or f"source_paper_fact_{i + 1:03d}",
                    "content": abstract[:600],
                    "fact_text": abstract[:1200],
                    "source_chunk_id": chunk_id,
                    "source_paper_title": title,
                    "quote_text": abstract[:240],
                    "relevance_score": paper.get("relevance_score"),
                    "source": paper.get("source") or "source_paper",
                    "document_id": paper.get("document_id") or paper.get("paper_id"),
                    "tier": "auxiliary",
                    "no_pdf": True if synthetic or paper.get("no_pdf") else bool(paper.get("no_pdf")),
                    "evidence_level": "abstract",
                },
            )

    # citation_map 中已有文献但无 fact 时，用摘要补一条（须过相关性门槛）
    for i, cit in enumerate(citation_map):
        title = (cit.get("title") or cit.get("paper_title") or "").strip()
        abstract = (cit.get("abstract") or "").strip()
        if not title or not abstract:
            continue
        if any((f.get("source_paper_title") or "").strip().lower() == title.lower() for f in facts):
            continue
        if not _can_promote_abstract_to_fact(cit):
            continue
        chunk_id, synthetic = _resolve_abstract_chunk_id(cit, index=i, prefix="abstract_cite")
        _append_fact(
            facts,
            seen_fact_ids,
            seen_chunks,
            {
                "fact_id": f"citation_fact_{i + 1:03d}",
                "content": abstract[:600],
                "fact_text": abstract[:1200],
                "source_chunk_id": chunk_id,
                "source_paper_title": title,
                "document_id": cit.get("document_id"),
                "quote_text": abstract[:240],
                "relevance_score": cit.get("relevance_score"),
                "source": cit.get("source_type") or "citation_map",
                "tier": "auxiliary",
                "no_pdf": True if synthetic or cit.get("no_pdf") else bool(cit.get("no_pdf")),
                "evidence_level": "abstract",
            },
        )

    if not verified and citation_map:
        verified = list(citation_map)

    # 已有 citation / verified 也可能缺 document_id（仅标题条目）
    citation_map = [
        ensure_citation_document_id(c, index=i) for i, c in enumerate(citation_map)
    ]
    verified = [
        ensure_citation_document_id(c, index=i) for i, c in enumerate(verified)
    ]

    return facts, citation_map, verified


def project_documents_as_citations(db: Any, project_id: str) -> List[Dict[str, Any]]:
    """将项目文献库中已处理的文档转为 citation_map / verified_references 条目。"""
    if not db or not project_id:
        return []
    try:
        from app.models.project import Document, DocumentStatus
    except Exception:
        logger.warning("导入 Document 模型失败，无法构建 citation", exc_info=True)
        return []

    rows = (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .filter(Document.status == DocumentStatus.PROCESSED)
        .order_by(Document.created_at.asc())
        .all()
    )
    entries: List[Dict[str, Any]] = []
    for doc in rows:
        title = (doc.title or "").strip()
        filename = (doc.filename or "").strip()
        meta = getattr(doc, "extra_metadata", None)
        if not isinstance(meta, dict):
            meta = {}
        pdf_meta = meta.get("pdf_metadata") if isinstance(meta, dict) else {}
        if not isinstance(pdf_meta, dict):
            pdf_meta = {}
        meta_title = str(pdf_meta.get("title") or "").strip()
        meta_author = str(pdf_meta.get("author") or "").strip()

        def _bad_title(value: str) -> bool:
            text = (value or "").strip()
            if not text or len(text) > 240 or text.count("\n") >= 2:
                return True
            # 期刊页眉：Journal Name 102 (2022) 164–176
            if re.search(r"\b\d{2,4}\s*\(\d{4}\)\s*\d+", text):
                return True
            low = text.lower()
            return low.startswith(("available online", "research paper", "http"))

        # PDF 解析偶发把页眉/正文塞进 title；优先内嵌 metadata，再回退文件名
        if _bad_title(title) and meta_title and not _bad_title(meta_title):
            title = meta_title
        elif _bad_title(title):
            title = filename.rsplit(".", 1)[0] if filename else title
        elif meta_title and not _bad_title(meta_title) and len(meta_title) > len(title) + 10:
            title = meta_title
        if not title:
            continue
        authors_raw = doc.authors or ""
        if isinstance(authors_raw, list):
            authors = ", ".join(str(a) for a in authors_raw if a)
        else:
            authors = str(authors_raw).strip()
        # authors 字段被 PDF 正文污染时丢弃，避免参考文献变成大段正文
        if (
            len(authors) > 180
            or authors.count("\n") >= 2
            or authors.lower().startswith(("http", "published by", "received", "available online", "©"))
            or "creativecommons" in authors.lower()
            or "open access article" in authors.lower()
        ):
            authors = meta_author if meta_author and len(meta_author) <= 180 else ""
        elif not authors and meta_author and len(meta_author) <= 180:
            authors = meta_author
        year = None
        if doc.publication_date:
            year = str(doc.publication_date)[:4]
        abstract = (doc.abstract or "").strip()
        if len(abstract) > 1200:
            abstract = abstract[:1200]
        summary = (getattr(doc, "summary", None) or "").strip()
        if len(summary) > 1200:
            summary = summary[:1200]
        entries.append(
            {
                "document_id": doc.id,
                "title": title,
                "paper_title": title,
                "authors": authors,
                "year": year,
                "doi": doc.doi,
                "abstract": abstract,
                "summary": summary,
                "source_url": doc.source_url or doc.pdf_url,
                "external_id": doc.external_id,
                "source": getattr(doc.source_type, "value", None) or doc.source_type or "upload",
                "source_type": getattr(doc.source_type, "value", None) or doc.source_type or "upload",
                "filename": filename,
            }
        )
    return entries


def _load_document_chunk_texts(
    db: Any,
    document_id: str,
    *,
    limit: int = 3,
    min_chars: int = 40,
) -> List[Dict[str, Any]]:
    """读取已解析文档的前若干 chunk，供无摘要时回填假设生成用 facts。"""
    if not db or not document_id:
        return []
    try:
        from app.models.project import Chunk
    except Exception:
        logger.warning("导入 Chunk 模型失败 document_id=%s", document_id, exc_info=True)
        return []
    try:
        rows = (
            db.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index.asc())
            .limit(max(1, int(limit)))
            .all()
        )
    except Exception:
        logger.warning("查询 Chunk 失败 document_id=%s", document_id, exc_info=True)
        return []
    out: List[Dict[str, Any]] = []
    for row in rows:
        text = (getattr(row, "content", None) or "").strip()
        if len(text) < min_chars:
            continue
        out.append(
            {
                "chunk_id": getattr(row, "id", None),
                "chunk_index": getattr(row, "chunk_index", None),
                "content": text[:1200],
                "page_number": getattr(row, "page_number", None),
            }
        )
    return out


def merge_project_library_into_literature_mining(
    literature_mining: Optional[Dict[str, Any]],
    *,
    db: Any = None,
    project_id: Optional[str] = None,
    max_chunks_per_doc: int = 3,
) -> Dict[str, Any]:
    """
    用项目文献库回填 citation_map / verified_references / facts。

    场景：用户在文献挖掘之后才上传 PDF，或向量索引尚未就绪导致 mining 为空，
    假设生成 / 报告仍应能读到已入库文献与解析片段，避免「上传了却没用上」。
    """
    lm = enrich_literature_mining(literature_mining)
    if not db or not project_id:
        return lm

    library = project_documents_as_citations(db, project_id)
    if not library:
        return lm

    citation_map = _as_dict_list(lm.get("citation_map"))
    verified = _as_dict_list(lm.get("verified_references"))
    facts = _as_dict_list(lm.get("facts"))
    seen_fact_ids = {str(f.get("fact_id")) for f in facts if f.get("fact_id")}
    seen_chunks = {
        str(f.get("source_chunk_id") or f.get("chunk_id"))
        for f in facts
        if f.get("source_chunk_id") or f.get("chunk_id")
    }
    facts_doc_ids = {
        str(f.get("document_id"))
        for f in facts
        if f.get("document_id")
    }

    for i, entry in enumerate(library):
        _append_citation(citation_map, entry)
        _append_citation(verified, entry)
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        doc_id = str(entry.get("document_id") or "")
        # 文献挖掘已对该文档抽过 facts：只补 citation，避免重复灌入
        if doc_id and doc_id in facts_doc_ids:
            continue

        abstract = (entry.get("abstract") or "").strip()
        summary = (entry.get("summary") or "").strip()
        body = abstract or summary
        added_for_doc = 0

        if body:
            _append_fact(
                facts,
                seen_fact_ids,
                seen_chunks,
                {
                    "fact_id": f"library_fact_{i + 1:03d}",
                    "content": body[:600],
                    "fact_text": body[:1200],
                    "source_chunk_id": f"library_doc_{doc_id or i + 1}",
                    "source_paper_title": title,
                    "document_id": doc_id or None,
                    "quote_text": body[:240],
                    "confidence": 0.7 if abstract else 0.55,
                    "source": "project_library",
                    "evidence_level": "abstract" if abstract else "summary",
                    "tier": "auxiliary",
                    "no_pdf": True,
                },
            )
            added_for_doc += 1
            if doc_id:
                facts_doc_ids.add(doc_id)

        # 无摘要/摘要不够时：用解析 chunk 回填（手动上传 PDF 的主路径）
        if added_for_doc == 0 and doc_id:
            chunk_rows = _load_document_chunk_texts(
                db, doc_id, limit=max_chunks_per_doc
            )
            for j, ch in enumerate(chunk_rows):
                text = (ch.get("content") or "").strip()
                if not text:
                    continue
                chunk_id = str(ch.get("chunk_id") or f"library_chunk_{doc_id}_{j}")
                _append_fact(
                    facts,
                    seen_fact_ids,
                    seen_chunks,
                    {
                        "fact_id": f"library_chunk_fact_{i + 1:03d}_{j + 1:02d}",
                        "content": text[:600],
                        "fact_text": text[:1200],
                        "source_chunk_id": chunk_id,
                        "source_paper_title": title,
                        "document_id": doc_id,
                        "quote_text": text[:240],
                        "page_number": ch.get("page_number"),
                        "confidence": 0.75,
                        "source": "project_library_chunk",
                        "evidence_level": "chunk",
                        "tier": "auxiliary",
                    },
                )
                added_for_doc += 1
            if added_for_doc and doc_id:
                facts_doc_ids.add(doc_id)

    lm["facts"] = facts
    lm["citation_map"] = citation_map
    lm["verified_references"] = verified
    lm["verified_references_count"] = len(verified)
    lm["project_library_document_count"] = len(library)
    if not lm.get("imported_documents"):
        lm["imported_documents"] = len(library)
    if not lm.get("literature_import_count"):
        lm["literature_import_count"] = len(library)
    return sync_fact_counts(lm)


def enrich_literature_mining(literature_mining: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """归并文献 bundle 并写回 literature_mining 字典。"""
    lm = dict(literature_mining or {})
    facts, citation_map, verified = normalize_literature_bundle(lm)
    lm["facts"] = facts
    lm["citation_map"] = citation_map
    lm["verified_references"] = verified
    lm["verified_references_count"] = len(verified)
    if not lm.get("literature_search_count"):
        lm["literature_search_count"] = int(
            lm.get("candidate_references_count")
            or len(lm.get("retrieved_papers") or [])
            or 0
        )
    if lm.get("literature_import_count") is None or lm.get("literature_import_count") == 0:
        corpus = (lm.get("skill_outputs") or {}).get("corpus_auto_import") or {}
        if isinstance(corpus, dict) and corpus.get("imported") is not None:
            lm["literature_import_count"] = int(corpus.get("imported") or 0)
            lm["imported_documents"] = lm["literature_import_count"]
    if not lm.get("candidate_references_count"):
        lm["candidate_references_count"] = lm.get("literature_search_count")
    return sync_fact_counts(lm)
