"""Data Acquisition 发布门槛 — Phase 7 Release Gate"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


DEFAULT_GATE_CONFIG: Dict[str, Any] = {
    "min_merged_rows": 1,
    "require_table_provenance": True,
    "require_figure_manifest": True,
    "require_bundle_ready": False,
    "max_gap_rounds": 4,
}


def evaluate_release_gate(
    results: Dict[str, Any],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """评估 data finder 结果是否达到可交付门槛。"""
    cfg = {**DEFAULT_GATE_CONFIG, **(config or {})}
    checks: List[Dict[str, Any]] = []

    merged = results.get("merged") or {}
    row_count = int(merged.get("row_count") or 0)
    checks.append({
        "id": "merged_csv",
        "label": "合并 CSV 至少 1 行",
        "passed": row_count >= int(cfg["min_merged_rows"]),
        "detail": {"row_count": row_count},
    })

    tables = results.get("extracted_tables") or []
    prov_records = results.get("provenance") or []
    prov_ids = {str(p.get("record_id")) for p in prov_records if p.get("record_id")}
    if tables and cfg.get("require_table_provenance"):
        missing = [t.get("table_id") for t in tables if t.get("table_id") and str(t["table_id"]) not in prov_ids]
        checks.append({
            "id": "table_provenance",
            "label": "表格 provenance 覆盖",
            "passed": len(missing) == 0,
            "detail": {"tables": len(tables), "missing_provenance": missing[:5]},
        })
    elif not tables:
        checks.append({
            "id": "table_provenance",
            "label": "表格 provenance 覆盖",
            "passed": True,
            "detail": {"skipped": True, "reason": "无抽取表格"},
        })

    figures = results.get("figures") or []
    if figures and cfg.get("require_figure_manifest"):
        without = [f.get("figure_id") for f in figures if not f.get("extraction_manifest")]
        with_manifest = sum(1 for f in figures if f.get("extraction_manifest"))
        checks.append({
            "id": "figure_manifest",
            "label": "图表 100% 有 extraction manifest",
            "passed": with_manifest == len(figures),
            "detail": {"figures": len(figures), "with_manifest": with_manifest, "missing": without[:5]},
        })
    elif not figures:
        checks.append({
            "id": "figure_manifest",
            "label": "图表 extraction manifest",
            "passed": True,
            "detail": {"skipped": True, "reason": "无图表"},
        })

    coverage = results.get("coverage_report") or {}
    if coverage:
        checks.append({
            "id": "coverage_report",
            "label": "完备性报告已生成",
            "passed": coverage.get("completeness_score") is not None,
            "detail": {
                "completeness_score": coverage.get("completeness_score"),
                "data_spec_score": (coverage.get("data_spec_coverage") or {}).get("data_spec_score"),
            },
        })

    bundle = results.get("analysis_bundle") or {}
    if cfg.get("require_bundle_ready"):
        checks.append({
            "id": "analysis_bundle",
            "label": "Analysis Bundle 可下载",
            "passed": bool(bundle.get("ready")),
            "detail": {"reason": bundle.get("reason")},
        })

    gap_rounds = len(results.get("gap_enrichment_history") or [])
    if not gap_rounds:
        da = results.get("data_acquisition") or {}
        gap_rounds = int((da.get("stats") or {}).get("gap_rounds") or 0)
    max_rounds = int(cfg.get("max_gap_rounds") or 4)
    checks.append({
        "id": "gap_rounds",
        "label": f"Gap 闭环轮次 ≤ {max_rounds}",
        "passed": gap_rounds <= max_rounds,
        "detail": {"gap_rounds": gap_rounds},
    })

    passed = all(c.get("passed") for c in checks)
    failed = [c for c in checks if not c.get("passed")]

    return {
        "passed": passed,
        "checks": checks,
        "failed_count": len(failed),
        "failed_ids": [c["id"] for c in failed],
        "ready_for_report": passed and row_count >= 1,
    }
