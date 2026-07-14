"""Data Finder 完备性报告 — 含 DataSpec 对照"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


DOMAIN_CHECKLISTS: Dict[str, List[Dict[str, str]]] = {
    "general": [
        {"id": "project_literature", "label": "项目已导入文献/PDF"},
        {"id": "paper_data_links", "label": "论文内数据/代码链接"},
        {"id": "pdf_tables", "label": "PDF 表格抽取"},
        {"id": "schema_aligned", "label": "字段对齐"},
        {"id": "merged_csv", "label": "多源 CSV 合并"},
        {"id": "external_candidates", "label": "外部开放数据候选"},
    ],
    "federated_learning": [
        {"id": "project_literature", "label": "联邦相关文献"},
        {"id": "fl_schema", "label": "FL 标准字段对齐"},
        {"id": "client_or_party_id", "label": "client_id/party_id 字段"},
        {"id": "metric_columns", "label": "accuracy/comm 指标列"},
        {"id": "merged_csv", "label": "合并训练/评测 CSV"},
        {"id": "external_benchmark", "label": "外部 benchmark 候选"},
    ],
}


def _norm_col(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_")


def _column_aliases(data_spec: Dict[str, Any], field: str) -> Set[str]:
    aliases = {_norm_col(field)}
    syns = data_spec.get("column_synonyms") or {}
    if isinstance(syns, dict):
        for std, alts in syns.items():
            if _norm_col(std) == _norm_col(field):
                aliases.add(_norm_col(std))
                if isinstance(alts, list):
                    for a in alts:
                        aliases.add(_norm_col(str(a)))
            elif isinstance(alts, list) and any(_norm_col(str(a)) == _norm_col(field) for a in alts):
                aliases.add(_norm_col(std))
                aliases.add(_norm_col(field))
    return {a for a in aliases if a}


def _merged_column_set(merged: Dict[str, Any], alignments: List[Dict[str, Any]]) -> Set[str]:
    cols: Set[str] = set()
    for c in merged.get("columns") or []:
        if c and not str(c).startswith("_"):
            cols.add(_norm_col(str(c)))
    for a in alignments:
        for c in a.get("standard_columns") or []:
            if c:
                cols.add(_norm_col(str(c)))
    return cols


def _field_hit(field: str, merged_cols: Set[str], data_spec: Dict[str, Any]) -> bool:
    aliases = _column_aliases(data_spec, field)
    return bool(aliases & merged_cols)


def build_data_spec_coverage(
    data_spec: Dict[str, Any],
    results: Dict[str, Any],
) -> Dict[str, Any]:
    """将 DataSpec 中的实体/目标变量与已整合数据对照。"""
    spec = data_spec or {}
    merged = results.get("merged") or {}
    alignments = results.get("alignments") or []
    figures = results.get("figures") or []
    merged_cols = _merged_column_set(merged, alignments)

    entities = [str(x) for x in (spec.get("entities_of_interest") or []) if x]
    targets = [str(x) for x in (spec.get("target_variables") or []) if x]

    entity_checklist: List[Dict[str, Any]] = []
    for ent in entities:
        hit = _field_hit(ent, merged_cols, spec)
        entity_checklist.append({"field": ent, "label": f"实体/对齐字段 {ent}", "hit": hit})

    target_checklist: List[Dict[str, Any]] = []
    for tv in targets:
        hit = _field_hit(tv, merged_cols, spec)
        target_checklist.append({"field": tv, "label": f"目标变量 {tv}", "hit": hit})

    figures_with_manifest = sum(
        1 for f in figures if (f.get("extraction_manifest") or f.get("figure_id"))
    )
    figures_confirmed = sum(
        1 for f in figures
        if (f.get("extraction_manifest") or {}).get("validation", {}).get("status") == "confirmed"
        or f.get("review_status") == "confirmed"
    )

    source_hits = {
        "paper_table": len(results.get("extracted_tables") or []) > 0,
        "external": len(results.get("external_candidates") or []) > 0,
        "supplementary": bool((results.get("supplementary_fetch") or {}).get("tables_added")),
        "figure_series": len(figures) > 0,
    }
    preferred = spec.get("preferred_sources") or []
    preferred_checklist: List[Dict[str, Any]] = []
    for src in preferred[:8]:
        key = str(src).lower()
        hit = False
        if "pdf" in key or "paper" in key or "table" in key:
            hit = source_hits["paper_table"]
        elif any(x in key for x in ("zenodo", "figshare", "dryad", "repository", "open")):
            hit = source_hits["external"] or source_hits["supplementary"]
        elif "hugging" in key or "kaggle" in key or "benchmark" in key:
            hit = source_hits["external"]
        elif "supplement" in key:
            hit = source_hits["supplementary"]
        elif "figure" in key:
            hit = source_hits["figure_series"]
        preferred_checklist.append({"source": src, "hit": hit})

    checklist = entity_checklist + target_checklist
    if preferred_checklist:
        checklist.extend([
            {"field": p["source"], "label": f"偏好来源 {p['source']}", "hit": p["hit"]}
            for p in preferred_checklist
        ])

    hit_count = sum(1 for c in checklist if c.get("hit"))
    total = len(checklist) or 1
    score = round(100 * hit_count / total, 1) if checklist else None

    entity_hits = [c["field"] for c in entity_checklist if c.get("hit")]
    entity_misses = [c["field"] for c in entity_checklist if not c.get("hit")]
    target_hits = [c["field"] for c in target_checklist if c.get("hit")]
    target_misses = [c["field"] for c in target_checklist if not c.get("hit")]

    gaps: List[str] = []
    if entities and entity_misses:
        gaps.append(f"未在合并 CSV 中找到实体字段: {', '.join(entity_misses[:5])}")
    if targets and target_misses:
        gaps.append(f"未在合并 CSV 中找到目标变量: {', '.join(target_misses[:5])}")
    if figures and figures_with_manifest and figures_confirmed == 0:
        gaps.append("图表 extraction manifest 已生成，但尚无人工确认条目")

    return {
        "data_spec_score": score,
        "entities_requested": entities,
        "entities_hit": entity_hits,
        "entities_miss": entity_misses,
        "targets_requested": targets,
        "targets_hit": target_hits,
        "targets_miss": target_misses,
        "merged_columns_matched": sorted(merged_cols)[:30],
        "figures_with_manifest": figures_with_manifest,
        "figures_confirmed": figures_confirmed,
        "preferred_sources_checklist": preferred_checklist,
        "checklist": checklist,
        "gaps": gaps[:6],
    }


def build_source_availability(external_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """统计外部候选的来源可用性（诚实区分可导入 vs 仅索引/元数据）。"""
    from app.services.data_sources.base import normalize_legacy_candidate

    normalized = [normalize_legacy_candidate(c) for c in (external_candidates or [])]
    by_availability: Dict[str, int] = {}
    platforms: Dict[str, int] = {}
    for c in normalized:
        av = str(c.get("availability") or "unknown")
        by_availability[av] = by_availability.get(av, 0) + 1
        plat = str(c.get("source_platform") or "unknown")[:40]
        platforms[plat] = platforms.get(plat, 0) + 1

    importable = [c for c in normalized if c.get("import_supported")]
    imported = [c for c in normalized if c.get("imported")]

    return {
        "total": len(normalized),
        "importable_count": len(importable),
        "imported_count": len(imported),
        "catalog_only_count": by_availability.get("catalog_only", 0),
        "metadata_only_count": by_availability.get("metadata_only", 0),
        "search_and_import_count": by_availability.get("search_and_import", 0),
        "by_availability": by_availability,
        "by_platform": dict(sorted(platforms.items(), key=lambda x: -x[1])[:12]),
        "candidates_summary": [
            {
                "dataset_name": (c.get("dataset_name") or "")[:80],
                "source_platform": c.get("source_platform"),
                "availability": c.get("availability"),
                "import_supported": c.get("import_supported"),
                "imported": bool(c.get("imported")),
            }
            for c in normalized[:15]
        ],
    }


def build_coverage_report(
    results: Dict[str, Any],
    *,
    documents_count: int = 0,
    cleaning_report: Optional[Dict[str, Any]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成子领域数据发现完备性报告。"""
    project_mode = results.get("project_mode") or "general"
    checklist_tpl = DOMAIN_CHECKLISTS.get(project_mode, DOMAIN_CHECKLISTS["general"])

    paper_ext = results.get("paper_extractions") or []
    tables = results.get("extracted_tables") or []
    merged = results.get("merged") or {}
    external = results.get("external_candidates") or []
    source_availability = build_source_availability(external)
    importable_external = source_availability.get("importable_count", 0)
    alignments = results.get("alignments") or []
    figures = results.get("figures") or []

    hits: Dict[str, bool] = {
        "project_literature": documents_count > 0,
        "paper_data_links": any(
            (pe.get("data_links") or pe.get("code_links")) for pe in paper_ext
        ),
        "pdf_tables": len(tables) > 0,
        "schema_aligned": len(alignments) > 0 and any(
            a.get("standard_columns") for a in alignments
        ),
        "merged_csv": bool(merged.get("merged_csv_path") or merged.get("cleaned_csv_path")),
        "external_candidates": importable_external > 0 or source_availability.get("imported_count", 0) > 0,
        "external_benchmark": importable_external > 0 or source_availability.get("imported_count", 0) > 0,
        "fl_schema": any(
            "global_accuracy" in (a.get("standard_columns") or [])
            or "communication_cost_mb" in (a.get("standard_columns") or [])
            for a in alignments
        ),
        "client_or_party_id": any(
            c in (merged.get("columns") or [])
            for c in ("client_id", "party_id", "entity_id")
        ),
        "metric_columns": any(
            c in (merged.get("columns") or [])
            for c in ("global_accuracy", "accuracy", "f1_score", "communication_cost_mb")
        ),
    }

    domain_checklist: List[Dict[str, Any]] = []
    hit_count = 0
    for item in checklist_tpl:
        hit = hits.get(item["id"], False)
        if hit:
            hit_count += 1
        domain_checklist.append({**item, "hit": hit})

    completeness_score = round(100 * hit_count / max(len(checklist_tpl), 1), 1)

    data_spec = results.get("data_spec") or (results.get("data_requirements") or {}).get("data_spec") or {}
    data_spec_coverage = build_data_spec_coverage(data_spec, results)

    gaps: List[str] = []
    if not hits.get("project_literature"):
        gaps.append("请先上传 PDF/BibTeX 文献到项目库")
    if not hits.get("pdf_tables"):
        gaps.append("未抽取到 PDF 表格，可检查 PDF 是否含可解析表格")
    if not hits.get("merged_csv"):
        gaps.append("尚未生成合并 CSV，请执行抽取→对齐→合并")
    if not hits.get("external_candidates"):
        if source_availability.get("total", 0) > 0 and importable_external == 0:
            gaps.append(
                "命中外部候选但均不可自动导入（Kaggle 索引 / OpenAlex / GEO 等需手动处理）"
            )
        else:
            gaps.append("未命中可自动导入的外部开放数据候选（HF/Zenodo 等）")
    for g in data_spec_coverage.get("gaps") or []:
        if g not in gaps:
            gaps.append(g)

    req = results.get("data_requirements") or {}
    queries = list(req.get("dataset_keywords") or [])[:6]
    queries.extend(list(req.get("domain_keywords") or [])[:4])

    thr = thresholds or {}
    from app.services.data_finder_gap_search import (
        DEFAULT_COVERAGE_THRESHOLD,
        DEFAULT_DATA_SPEC_THRESHOLD,
        should_run_gap_enrichment,
    )

    report: Dict[str, Any] = {
        "completeness_score": completeness_score,
        "data_spec_coverage": data_spec_coverage,
        "threshold": float(thr.get("coverage_gap_threshold") or DEFAULT_COVERAGE_THRESHOLD),
        "data_spec_threshold": float(thr.get("data_spec_gap_threshold") or DEFAULT_DATA_SPEC_THRESHOLD),
        "project_mode": project_mode,
        "queries_executed": queries,
        "documents_count": documents_count,
        "papers_screened": len(paper_ext),
        "papers_with_data_links": sum(
            1 for pe in paper_ext if (pe.get("data_links") or pe.get("code_links"))
        ),
        "tables_extracted": len(tables),
        "figures_metadata": len(figures),
        "rows_merged": merged.get("row_count") or 0,
        "external_candidates_count": len(external),
        "external_import_succeeded": source_availability.get("imported_count", 0),
        "source_availability": source_availability,
        "domain_checklist": domain_checklist,
        "gaps": gaps[:8],
        "cleaning_summary": cleaning_report or {},
        "has_cleaned_csv": bool(merged.get("cleaned_csv_path")),
    }
    report["gap_enrichment_recommended"] = should_run_gap_enrichment(
        report,
        threshold=report["threshold"],
        data_spec_threshold=report["data_spec_threshold"],
    )
    return report
