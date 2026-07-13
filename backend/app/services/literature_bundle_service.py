"""文献挖掘结果归并：将 facts / citation_map / skill 输出统一为下游可消费结构。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _as_dict_list(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            out.append(dict(item))
        elif hasattr(item, "model_dump"):
            out.append(item.model_dump())
    return out


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
    citation_map.append(entry)


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
        if abstract:
            _append_fact(
                facts,
                seen_fact_ids,
                seen_chunks,
                {
                    "fact_id": f"paper_fact_{i + 1:03d}",
                    "content": abstract[:600],
                    "fact_text": abstract[:1200],
                    "source_chunk_id": f"paper_{i + 1}",
                    "source_paper_title": title,
                    "quote_text": abstract[:240],
                    "confidence": 0.75,
                    "source": paper.get("source") or "retrieved_paper",
                    "document_id": paper.get("document_id") or paper.get("paper_id"),
                    "year": paper.get("year"),
                    "doi": paper.get("doi"),
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
        if abstract:
            _append_fact(
                facts,
                seen_fact_ids,
                seen_chunks,
                {
                    "fact_id": paper.get("fact_id") or f"source_paper_fact_{i + 1:03d}",
                    "content": abstract[:600],
                    "fact_text": abstract[:1200],
                    "source_chunk_id": paper.get("source_chunk_id") or f"source_paper_{i + 1}",
                    "source_paper_title": title,
                    "quote_text": abstract[:240],
                    "source": paper.get("source") or "source_paper",
                },
            )

    # citation_map 中已有文献但无 fact 时，用摘要补一条
    for i, cit in enumerate(citation_map):
        title = (cit.get("title") or cit.get("paper_title") or "").strip()
        abstract = (cit.get("abstract") or "").strip()
        if not title or not abstract:
            continue
        if any((f.get("source_paper_title") or "").strip().lower() == title.lower() for f in facts):
            continue
        _append_fact(
            facts,
            seen_fact_ids,
            seen_chunks,
            {
                "fact_id": f"citation_fact_{i + 1:03d}",
                "content": abstract[:600],
                "fact_text": abstract[:1200],
                "source_chunk_id": f"citation_{cit.get('document_id') or i + 1}",
                "source_paper_title": title,
                "document_id": cit.get("document_id"),
                "quote_text": abstract[:240],
                "source": cit.get("source_type") or "citation_map",
            },
        )

    if not verified and citation_map:
        verified = list(citation_map)

    return facts, citation_map, verified


def enrich_literature_mining(literature_mining: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """归并文献 bundle 并写回 literature_mining 字典。"""
    lm = dict(literature_mining or {})
    facts, citation_map, verified = normalize_literature_bundle(lm)
    lm["facts"] = facts
    lm["citation_map"] = citation_map
    lm["verified_references"] = verified
    lm["evidence_facts"] = len(facts)
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
    return lm
