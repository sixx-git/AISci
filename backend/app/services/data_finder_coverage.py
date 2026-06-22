"""Data Finder 完备性报告"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


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


def build_coverage_report(
    results: Dict[str, Any],
    *,
    documents_count: int = 0,
    cleaning_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成子领域数据发现完备性报告。"""
    project_mode = results.get("project_mode") or "general"
    checklist_tpl = DOMAIN_CHECKLISTS.get(project_mode, DOMAIN_CHECKLISTS["general"])

    paper_ext = results.get("paper_extractions") or []
    tables = results.get("extracted_tables") or []
    merged = results.get("merged") or {}
    external = results.get("external_candidates") or []
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
        "external_candidates": len(external) > 0,
        "external_benchmark": len(external) > 0,
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

    gaps: List[str] = []
    if not hits.get("project_literature"):
        gaps.append("请先上传 PDF/BibTeX 文献到项目库")
    if not hits.get("pdf_tables"):
        gaps.append("未抽取到 PDF 表格，可检查 PDF 是否含可解析表格")
    if not hits.get("merged_csv"):
        gaps.append("尚未生成合并 CSV，请执行抽取→对齐→合并")
    if not hits.get("external_candidates"):
        gaps.append("未命中外部开放数据库候选（OpenAlex/HF 等）")
    if project_mode == "federated_learning" and not hits.get("fl_schema"):
        gaps.append("联邦标准字段未对齐，请检查 CSV 列名或上传 FL benchmark 表")

    req = results.get("data_requirements") or {}
    queries = list(req.get("dataset_keywords") or [])[:6]
    queries.extend(list(req.get("domain_keywords") or [])[:4])

    return {
        "completeness_score": completeness_score,
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
        "external_import_succeeded": 0,
        "domain_checklist": domain_checklist,
        "gaps": gaps[:6],
        "cleaning_summary": cleaning_report or {},
        "has_cleaned_csv": bool(merged.get("cleaned_csv_path")),
    }
