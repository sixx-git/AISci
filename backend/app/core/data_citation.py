"""data_citation_id / table_row_id 追溯工具"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def resolve_data_citation(
    citation_id: str,
    *,
    provenance: Optional[List[Dict[str, Any]]] = None,
    row_provenance: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """按 data_citation_id 查找 provenance 记录（表级或行级）。"""
    if not citation_id:
        return None
    for rec in row_provenance or []:
        if str(rec.get("data_citation_id")) == citation_id:
            return {**rec, "level": "row"}
    for rec in provenance or []:
        if str(rec.get("data_citation_id")) == citation_id:
            return {**rec, "level": "table"}
    return None


def collect_citation_ids_from_hypothesis(hypo: Dict[str, Any]) -> List[str]:
    """从假设字段中提取 data_citation_id 引用。"""
    ids: List[str] = []
    for cid in hypo.get("data_citation_ids") or []:
        if cid:
            ids.append(str(cid))
    for ref in hypo.get("dataset_field_refs") or []:
        ref_s = str(ref)
        if ref_s.startswith("cite_"):
            ids.append(ref_s)
    spec = hypo.get("verifiable_spec") or {}
    for ref in spec.get("dataset_field_refs") or []:
        ref_s = str(ref)
        if ref_s.startswith("cite_"):
            ids.append(ref_s)
    return list(dict.fromkeys(ids))
