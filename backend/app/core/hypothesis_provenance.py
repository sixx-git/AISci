"""假设溯源时间线 — facts → 多模态 → 数据集 → verifiable spec"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fact_lookup(facts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for fact in facts or []:
        fid = fact.get("fact_id")
        if fid:
            index[str(fid)] = fact
    return index


def build_hypothesis_provenance_timeline(
    hypo: Dict[str, Any],
    *,
    facts: Optional[List[Dict[str, Any]]] = None,
    multimodal_facts: Optional[List[Dict[str, Any]]] = None,
    row_provenance: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """构建假设溯源时间线，供前端 Tab 展示与跳转。"""
    timeline: List[Dict[str, Any]] = []
    fact_by_id = _fact_lookup(facts or [])

    fact_ids = list(hypo.get("supporting_fact_ids") or [])
    if fact_ids:
        items: List[Dict[str, Any]] = []
        for fid in fact_ids:
            fact = fact_by_id.get(str(fid), {})
            items.append({
                "fact_id": fid,
                "content": (fact.get("content") or fact.get("fact_text") or "")[:240],
                "source_title": fact.get("source_paper_title") or fact.get("title") or "",
                "document_id": fact.get("document_id") or fact.get("source_document_id") or "",
                "chunk_id": fact.get("source_chunk_id") or fact.get("chunk_id") or "",
                "page": fact.get("page_number") or fact.get("page"),
            })
        timeline.append({
            "step": "literature_facts",
            "label": "文献事实",
            "count": len(items),
            "items": items,
        })

    data_evidence_ids = list(hypo.get("data_evidence_ids") or [])
    mm_index: Dict[str, Dict[str, Any]] = {}
    for mm in multimodal_facts or []:
        for key in (mm.get("fact_id"), mm.get("asset_id"), mm.get("evidence_id")):
            if key:
                mm_index[str(key)] = mm

    if data_evidence_ids:
        mm_items: List[Dict[str, Any]] = []
        for eid in data_evidence_ids:
            mm = mm_index.get(str(eid), {})
            mm_items.append({
                "evidence_id": eid,
                "modality": mm.get("modality") or "multimodal",
                "asset_id": mm.get("asset_id") or eid,
                "content": (mm.get("content") or mm.get("fact_text") or "")[:240],
                "source_title": mm.get("source_paper_title") or mm.get("filename") or "",
            })
        timeline.append({
            "step": "multimodal",
            "label": "多模态证据",
            "count": len(mm_items),
            "items": mm_items,
        })

    field_refs = list(hypo.get("dataset_field_refs") or [])
    citation_ids = list(hypo.get("data_citation_ids") or [])
    cite_index = {
        str(r.get("data_citation_id")): r
        for r in (row_provenance or [])
        if r.get("data_citation_id")
    }
    if field_refs or citation_ids:
        data_items: List[Dict[str, Any]] = []
        for ref in field_refs:
            data_items.append({
                "ref": ref,
                "kind": "field_ref",
                "data_citation_id": ref if str(ref).startswith("cite_") else "",
            })
        for cid in citation_ids:
            prov = cite_index.get(str(cid), {})
            data_items.append({
                "ref": cid,
                "kind": "data_citation",
                "data_citation_id": cid,
                "table_row_id": prov.get("table_row_id"),
                "source_title": prov.get("source_title") or "",
                "table_id": prov.get("table_id") or prov.get("record_id"),
            })
        timeline.append({
            "step": "dataset",
            "label": "数据集字段",
            "count": len(data_items),
            "items": data_items,
        })

    spec = hypo.get("verifiable_spec") or {}
    if spec:
        timeline.append({
            "step": "verifiable_spec",
            "label": "可验证 spec",
            "count": 1,
            "items": [{
                "claim": spec.get("claim") or "",
                "primary_metric": spec.get("primary_metric") or "",
                "falsification_criteria": spec.get("falsification_criteria") or "",
                "success_criteria": (spec.get("success_criteria") or [])[:4],
                "supporting_fact_ids": (spec.get("supporting_fact_ids") or [])[:8],
                "dataset_field_refs": (spec.get("dataset_field_refs") or [])[:8],
            }],
        })

    return timeline
