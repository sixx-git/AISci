"""Data Finder 结果瘦身 — 避免将合并表/逐行溯源写入 SQLite。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

_MAX_LIST_ITEMS = 20
_MAX_STR_LEN = 2000


def _truncate_str(val: Any, limit: int = _MAX_STR_LEN) -> Any:
    if isinstance(val, str) and len(val) > limit:
        return val[:limit] + "…"
    return val


def slim_merged_block(merged: Any) -> Dict[str, Any]:
    if not isinstance(merged, dict):
        return {}
    out: Dict[str, Any] = {
        "csv_path": merged.get("csv_path"),
        "row_count": merged.get("row_count"),
        "column_count": merged.get("column_count") or len(merged.get("columns") or []),
        "columns": list(merged.get("columns") or [])[:80],
        "merge_strategy": merged.get("merge_strategy"),
        "quality_score": merged.get("quality_score"),
    }
    preview = merged.get("preview") or merged.get("rows") or merged.get("data")
    if isinstance(preview, list) and preview:
        out["preview_rows"] = preview[:5]
    prov = merged.get("row_provenance")
    if isinstance(prov, list):
        out["row_provenance_count"] = len(prov)
        out["row_provenance_sample"] = prov[:3]
    elif prov is not None:
        out["row_provenance"] = _truncate_str(prov)
    return {k: v for k, v in out.items() if v is not None}


def slim_table_entry(table: Any) -> Dict[str, Any]:
    if not isinstance(table, dict):
        return {}
    return {
        "table_id": table.get("table_id"),
        "source_title": table.get("source_title"),
        "caption": table.get("caption"),
        "csv_path": table.get("csv_path"),
        "columns": list(table.get("columns") or [])[:80],
        "row_count": table.get("row_count"),
        "quality_score": table.get("quality_score"),
        "extraction_method": table.get("extraction_method"),
        "candidate_id": table.get("candidate_id"),
    }


def slim_data_finder_payload(payload: Any) -> Dict[str, Any]:
    """将 data_finder / results.json 转为可安全持久化到 DB 的摘要。"""
    if not isinstance(payload, dict):
        return {}

    slim: Dict[str, Any] = {
        "project_id": payload.get("project_id"),
        "project_mode": payload.get("project_mode"),
        "updated_at": payload.get("updated_at"),
        "warnings": list(payload.get("warnings") or [])[:10],
    }

    if payload.get("data_spec"):
        spec = payload["data_spec"]
        if isinstance(spec, dict):
            slim["data_spec"] = {
                "dataset_keywords": (spec.get("dataset_keywords") or [])[:15],
                "domain_keywords": (spec.get("domain_keywords") or [])[:15],
                "modality_filter": spec.get("modality_filter"),
            }

    merged = payload.get("merged")
    if merged:
        slim["merged"] = slim_merged_block(merged)

    tables = payload.get("extracted_tables")
    if isinstance(tables, list):
        slim["extracted_tables"] = [slim_table_entry(t) for t in tables[:_MAX_LIST_ITEMS]]
        slim["extracted_tables_count"] = len(tables)

    candidates = payload.get("external_candidates")
    if isinstance(candidates, list):
        slim["external_candidates"] = [
            {
                "candidate_id": c.get("candidate_id"),
                "dataset_name": c.get("dataset_name"),
                "source_platform": c.get("source_platform"),
                "user_upload_status": c.get("user_upload_status"),
                "linked_table_id": c.get("linked_table_id"),
                "imported_csv_path": c.get("imported_csv_path"),
            }
            for c in candidates[:_MAX_LIST_ITEMS]
        ]
        slim["external_candidates_count"] = len(candidates)

    prov = payload.get("provenance")
    if isinstance(prov, list):
        slim["provenance_count"] = len(prov)
        slim["provenance_sample"] = prov[:5]

    da = payload.get("data_acquisition")
    if isinstance(da, dict):
        slim["data_acquisition"] = {
            k: _truncate_str(v) if not isinstance(v, (dict, list)) else v
            for k, v in da.items()
            if k not in ("raw_payload", "full_results")
        }
        if isinstance(da.get("step_details"), dict):
            slim["data_acquisition"]["step_details"] = {
                k: v for k, v in da["step_details"].items()
                if k != "gap_loop" or not isinstance(v, list) or len(v) <= 5
            }

    return slim


def slim_data_acquisition_output(output: Any) -> Dict[str, Any]:
    """Pipeline data_acquisition / data_finder 阶段输出摘要。"""
    if not isinstance(output, dict):
        return {}
    final = output.get("search") or output.get("extract") or output
    slim_final = slim_data_finder_payload(final if isinstance(final, dict) else {})
    return {
        "data_acquisition": output.get("data_acquisition") if isinstance(output.get("data_acquisition"), dict) else slim_final.get("data_acquisition"),
        "search_summary": slim_final,
        "paper_link_extractions_count": len(output.get("paper_link_extractions") or []),
        "refinement_queries": list(output.get("refinement_queries") or [])[:8],
        "gap_enrichment": output.get("gap_enrichment") if isinstance(output.get("gap_enrichment"), dict) else {},
    }


def slim_results_for_checkpoint(results: Dict[str, Any]) -> Dict[str, Any]:
    """Checkpoint / stage 输入持久化前的 results 瘦身。"""
    safe: Dict[str, Any] = {}
    for key, val in results.items():
        if key in ("data_finder", "data_acquisition"):
            safe[key] = slim_data_acquisition_output(val if isinstance(val, dict) else {})
        elif key == "literature_mining" and isinstance(val, dict):
            lm = dict(val)
            so = lm.get("skill_outputs")
            if isinstance(so, dict):
                lm["skill_outputs"] = {
                    k: {"success": (v or {}).get("success"), "data_keys": list(((v or {}).get("data") or {}).keys())[:12]}
                    if isinstance(v, dict) else v
                    for k, v in so.items()
                }
            safe[key] = lm
        elif isinstance(val, (dict, list, str, int, float, bool)) or val is None:
            try:
                blob = json.dumps(val, ensure_ascii=False)
                if len(blob) > 200_000:
                    safe[key] = {"_truncated": True, "preview": _truncate_str(blob, 8000)}
                else:
                    safe[key] = val
            except (TypeError, ValueError):
                safe[key] = _truncate_str(str(val))
        else:
            safe[key] = _truncate_str(str(val))
    return safe


def slim_stage_input(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """阶段 input_data 写入 DB 前瘦身。"""
    if not isinstance(input_data, dict):
        return {}
    out = dict(input_data)
    if "data_finder" in out:
        out["data_finder"] = slim_data_acquisition_output(out.get("data_finder") or {})
    if "literature_mining" in out and isinstance(out["literature_mining"], dict):
        lm = dict(out["literature_mining"])
        papers = lm.get("source_papers") or lm.get("retrieved_papers")
        if isinstance(papers, list) and len(papers) > _MAX_LIST_ITEMS:
            lm["source_papers"] = papers[:_MAX_LIST_ITEMS]
            lm["source_papers_count"] = len(papers)
        out["literature_mining"] = lm
    try:
        if len(json.dumps(out, ensure_ascii=False)) > 500_000:
            return {
                "project_id": out.get("project_id"),
                "research_question": _truncate_str(out.get("research_question"), 500),
                "project_mode": out.get("project_mode"),
                "data_context": out.get("data_context"),
                "_slimmed": True,
            }
    except (TypeError, ValueError):
        pass
    return out
