"""Data Finder 结果瘦身 — 避免将合并表/逐行溯源写入 SQLite。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

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
                "entities_of_interest": (spec.get("entities_of_interest") or [])[:8],
                "target_variables": (spec.get("target_variables") or [])[:10],
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


def slim_hypothesis_generation_for_checkpoint(output: Dict[str, Any]) -> Dict[str, Any]:
    """Checkpoint 保留完整 hypotheses 列表，仅裁剪非关键大块字段。"""
    if not isinstance(output, dict):
        return output if isinstance(output, dict) else {}
    out: Dict[str, Any] = {
        "summary": _truncate_str(output.get("summary"), 2000),
        "primary_verifiable_spec": output.get("primary_verifiable_spec"),
    }
    hyps = output.get("hypotheses") or []
    slim_hyps: List[Dict[str, Any]] = []
    for h in hyps:
        if not isinstance(h, dict):
            continue
        slim_hyps.append({
            "hypothesis": _truncate_str(h.get("hypothesis"), 4000),
            "rationale": _truncate_str(h.get("rationale"), 2000),
            "novelty": _truncate_str(h.get("novelty"), 1000),
            "testability": _truncate_str(h.get("testability"), 1000),
            "required_data": _truncate_str(h.get("required_data"), 1000),
            "possible_method": _truncate_str(h.get("possible_method"), 1000),
            "risk": _truncate_str(h.get("risk"), 1000),
            "supporting_fact_ids": list(h.get("supporting_fact_ids") or [])[:40],
            "validation_target": _truncate_str(h.get("validation_target"), 500),
            "expected_measurable_effect": _truncate_str(h.get("expected_measurable_effect"), 500),
            "evidence_level": h.get("evidence_level"),
            "verifiable_spec": h.get("verifiable_spec") if isinstance(h.get("verifiable_spec"), dict) else {},
            "alignment_score": h.get("alignment_score"),
            "off_topic": h.get("off_topic"),
        })
    out["hypotheses"] = slim_hyps

    align = output.get("alignment")
    if isinstance(align, dict):
        out["alignment"] = {
            "alignments": (align.get("alignments") or [])[:20],
            "summary": _truncate_str(align.get("summary"), 1000),
        }

    ht = output.get("hypothesis_tree")
    if isinstance(ht, dict):
        branches = ht.get("branches") or []
        out["hypothesis_tree"] = {
            "summary": _truncate_str(ht.get("summary"), 1000),
            "branches": [
                {
                    "hypothesis_index": b.get("hypothesis_index"),
                    "composite_score": b.get("composite_score"),
                    "hypothesis": _truncate_str(b.get("hypothesis"), 800),
                }
                for b in branches[:5]
                if isinstance(b, dict)
            ],
        }
    return out


def slim_results_for_checkpoint(results: Dict[str, Any]) -> Dict[str, Any]:
    """Checkpoint / stage 输入持久化前的 results 瘦身。"""
    safe: Dict[str, Any] = {}
    for key, val in results.items():
        if key in ("data_finder", "data_acquisition"):
            safe[key] = slim_data_acquisition_output(val if isinstance(val, dict) else {})
        elif key == "hypothesis_generation" and isinstance(val, dict):
            safe[key] = slim_hypothesis_generation_for_checkpoint(val)
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


def slim_data_context(context: Any) -> Dict[str, Any]:
    """项目 data_context 写入 Pipeline 输入前瘦身（避免 SQLite 膨胀）。"""
    if not isinstance(context, dict):
        return {}
    slim: Dict[str, Any] = {
        "dataset_count": context.get("dataset_count"),
        "available_modalities": list(context.get("available_modalities") or [])[:12],
        "field_candidates": list(context.get("field_candidates") or [])[:40],
        "target_candidates": list(context.get("target_candidates") or [])[:20],
        "quality_summary": context.get("quality_summary") if isinstance(context.get("quality_summary"), dict) else {},
        "warnings": list(context.get("warnings") or [])[:8],
        "project_mode": context.get("project_mode"),
        "data_finder_merged_csv": context.get("data_finder_merged_csv"),
        "fl_context": context.get("fl_context") if isinstance(context.get("fl_context"), dict) else None,
    }
    datasets = context.get("datasets")
    if isinstance(datasets, list):
        slim["datasets"] = [
            {
                "dataset_id": d.get("dataset_id"),
                "filename": d.get("filename"),
                "file_path": d.get("file_path"),
                "data_type": d.get("data_type"),
                "n_rows": d.get("n_rows"),
                "n_columns": d.get("n_columns"),
                "columns": list(d.get("columns") or [])[:40],
                "missing_rate": d.get("missing_rate"),
                "preprocessing_status": d.get("preprocessing_status"),
                "use_for_hypothesis": d.get("use_for_hypothesis"),
            }
            for d in datasets[:12]
            if isinstance(d, dict)
        ]
    df = context.get("data_finder_results")
    if isinstance(df, dict):
        slim["data_finder_results"] = slim_data_finder_payload(df)
    mm = context.get("multimodal_evidence")
    if isinstance(mm, list):
        slim["multimodal_evidence_count"] = len(mm)
        slim["multimodal_evidence"] = mm[:8]
    return {k: v for k, v in slim.items() if v is not None}


def slim_literature_mining_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """文献挖掘阶段持久化：保留 facts/uncertain_points 供下游与 UI，瘦身大字段。"""
    if not isinstance(output, dict):
        return {}
    if output.get("_truncated"):
        return output

    lm = dict(output)
    papers = lm.get("source_papers") or lm.get("retrieved_papers")
    if isinstance(papers, list) and len(papers) > _MAX_LIST_ITEMS:
        lm["source_papers"] = papers[:_MAX_LIST_ITEMS]
        lm["source_papers_count"] = len(papers)

    facts = lm.get("facts")
    if isinstance(facts, list):
        slim_facts: List[Dict[str, Any]] = []
        for f in facts[:50]:
            if not isinstance(f, dict):
                continue
            slim_facts.append({
                **{k: v for k, v in f.items() if k not in ("fact_text", "quote_text", "content")},
                "content": _truncate_str(f.get("content") or f.get("fact_text"), 800),
                "fact_text": _truncate_str(f.get("fact_text") or f.get("content"), 1200),
                "quote_text": _truncate_str(f.get("quote_text"), 300),
            })
        lm["facts"] = slim_facts
        if len(facts) > 50:
            lm["facts_count"] = len(facts)

    uncertain = lm.get("uncertain_points")
    if isinstance(uncertain, list) and len(uncertain) > 30:
        lm["uncertain_points"] = uncertain[:30]
        lm["uncertain_points_count"] = len(uncertain)

    evidence = lm.get("evidence")
    if isinstance(evidence, list):
        lm["evidence_count"] = len(evidence)
        lm["evidence"] = evidence[:10]

    citation_map = lm.get("citation_map")
    if isinstance(citation_map, list):
        lm["citation_map_count"] = len(citation_map)
        lm["citation_map"] = citation_map[:15]

    so = lm.get("skill_outputs")
    if isinstance(so, dict):
        lm["skill_outputs"] = {
            k: {"success": (v or {}).get("success"), "data_keys": list(((v or {}).get("data") or {}).keys())[:12]}
            if isinstance(v, dict) else v
            for k, v in so.items()
        }
    return lm


def _report_payload_usable(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("paper_title") or data.get("title"):
        return True
    chapters = data.get("chapters")
    return isinstance(chapters, dict) and any(chapters.values())


def _try_parse_json_text(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def slim_report_generation_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """报告阶段持久化：保留章节结构与元数据，截断超长文本。"""
    if not isinstance(output, dict):
        return {}
    if output.get("_truncated"):
        return output

    slim: Dict[str, Any] = {
        k: output[k]
        for k in (
            "title",
            "paper_title",
            "paper_abstract",
            "report_id",
            "pdf_success",
            "export_method",
            "warning",
            "human_review_required",
            "report_mode",
            "compliance_check",
        )
        if k in output
    }
    if isinstance(output.get("paper_abstract"), str):
        slim["paper_abstract"] = _truncate_str(output["paper_abstract"], 8000)

    chapters = output.get("chapters")
    if isinstance(chapters, dict):
        slim_chapters: Dict[str, Any] = {}
        for key, val in chapters.items():
            if key == "references" and isinstance(val, list):
                slim_chapters[key] = val[:80]
                if len(val) > 80:
                    slim_chapters["references_count"] = len(val)
            else:
                slim_chapters[key] = _truncate_str(val, 12000)
        slim["chapters"] = slim_chapters

    plots = output.get("plots")
    if isinstance(plots, list):
        from app.services.report_plot_service import slim_plot_for_db

        slim["plots"] = [slim_plot_for_db(p) for p in plots[:30] if isinstance(p, dict)]
        slim["plots_count"] = len(plots)

    return slim


def resolve_report_generation_payload(
    report_data: Any,
    *,
    memory_fallback: Any = None,
    storage_fallback: Any = None,
) -> Dict[str, Any]:
    """从阶段输出、内存缓存或磁盘 JSON 恢复可落库的报告结构。"""
    ordered: List[Dict[str, Any]] = []

    if isinstance(memory_fallback, dict) and _report_payload_usable(memory_fallback):
        ordered.append(memory_fallback)

    if isinstance(report_data, dict) and report_data:
        if not report_data.get("_truncated"):
            ordered.append(report_data)
        else:
            preview = _try_parse_json_text(report_data.get("preview") or "")
            if preview:
                ordered.append(preview)
            elif report_data.get("report_id"):
                disk = load_report_data_from_storage(str(report_data["report_id"]))
                if disk:
                    ordered.append(disk)

    if isinstance(storage_fallback, dict) and _report_payload_usable(storage_fallback):
        ordered.append(storage_fallback)

    for resolved in ordered:
        if _report_payload_usable(resolved):
            return resolved
    return {}


def load_report_data_from_storage(report_file_id: str) -> Dict[str, Any]:
    """读取报告生成阶段写入的 report_data.json。"""
    if not report_file_id:
        return {}
    try:
        from app.services.latex_export_service import get_reports_storage_dir

        json_path = get_reports_storage_dir() / report_file_id / "report_data.json"
        if not json_path.is_file():
            return {}
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def find_recent_report_data_on_disk(
    *,
    not_before_ts: Optional[float] = None,
    not_after_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """按修改时间扫描磁盘报告，用于 Pipeline 落库补偿。"""
    try:
        from app.services.latex_export_service import get_reports_storage_dir

        root = get_reports_storage_dir()
        if not root.is_dir():
            return {}
        best: tuple[float, Dict[str, Any]] = (0.0, {})
        for child in root.iterdir():
            if not child.is_dir():
                continue
            json_path = child / "report_data.json"
            if not json_path.is_file():
                continue
            mtime = json_path.stat().st_mtime
            if not_before_ts is not None and mtime < not_before_ts:
                continue
            if not_after_ts is not None and mtime > not_after_ts:
                continue
            if mtime <= best[0]:
                continue
            data = load_report_data_from_storage(child.name)
            if _report_payload_usable(data):
                best = (mtime, data)
        return best[1]
    except Exception:
        return {}


def slim_stage_output(output: Any, stage_key: str = "") -> Any:
    """阶段 output_data 持久化到 DB 前瘦身。"""
    if output is None:
        return None
    if not isinstance(output, dict):
        return _truncate_str(output) if isinstance(output, str) else output

    key = (stage_key or "").lower()
    if key in ("data_acquisition", "data_finder"):
        return slim_data_acquisition_output(output)
    if key == "literature_mining":
        output = slim_literature_mining_output(output)
    elif key == "report_generation":
        output = slim_report_generation_output(output)
    elif key == "experiment_design":
        ed = dict(output)
        so = ed.get("skill_outputs")
        if isinstance(so, dict):
            slim_so = {}
            for sk, val in so.items():
                if not isinstance(val, dict):
                    slim_so[sk] = val
                    continue
                data = val.get("data")
                if sk == "dataset_discovery" and isinstance(data, dict):
                    slim_so[sk] = {**val, "data": {"datasets": (data.get("datasets") or [])[:5]}}
                elif isinstance(data, dict) and len(json.dumps(data, ensure_ascii=False)) > 20_000:
                    slim_so[sk] = {**val, "data": {"_truncated": True, "keys": list(data.keys())[:20]}}
                else:
                    slim_so[sk] = val
            ed["skill_outputs"] = slim_so
        output = ed

    try:
        blob = json.dumps(output, ensure_ascii=False)
        if len(blob) <= 120_000:
            return output
    except (TypeError, ValueError):
        return {"_truncated": True, "preview": _truncate_str(str(output), 4000)}

    if key == "literature_mining" and isinstance(output, dict):
        return slim_literature_mining_output(output)
    if key == "report_generation" and isinstance(output, dict):
        return slim_report_generation_output(output)

    wrapped = slim_results_for_checkpoint({"_stage": output})
    return wrapped.get("_stage", output)


def slim_stage_input(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """阶段 input_data 写入 DB 前瘦身。"""
    if not isinstance(input_data, dict):
        return {}
    out = dict(input_data)
    if "data_context" in out and isinstance(out["data_context"], dict):
        out["data_context"] = slim_data_context(out["data_context"])
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
