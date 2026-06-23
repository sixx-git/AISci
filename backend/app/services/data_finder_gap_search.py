"""Gap 驱动的外部数据补搜"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_COVERAGE_THRESHOLD = 70.0
DEFAULT_DATA_SPEC_THRESHOLD = 60.0


def resolve_gap_thresholds(
    project_config: Optional[Dict[str, Any]] = None,
    run_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """合并项目 config 与 Pipeline run_options 中的 gap 阈值。"""
    cfg = {}
    if isinstance(project_config, dict):
        cfg = project_config.get("data_acquisition") or {}
    opts = run_options or {}
    try:
        coverage_threshold = float(
            opts.get("coverage_gap_threshold")
            or cfg.get("coverage_gap_threshold")
            or DEFAULT_COVERAGE_THRESHOLD
        )
    except (TypeError, ValueError):
        coverage_threshold = DEFAULT_COVERAGE_THRESHOLD
    try:
        data_spec_threshold = float(
            opts.get("data_spec_gap_threshold")
            or cfg.get("data_spec_gap_threshold")
            or DEFAULT_DATA_SPEC_THRESHOLD
        )
    except (TypeError, ValueError):
        data_spec_threshold = DEFAULT_DATA_SPEC_THRESHOLD
    try:
        max_gap_rounds = int(opts.get("max_gap_rounds") or cfg.get("max_gap_rounds") or 2)
        max_gap_rounds = max(1, min(max_gap_rounds, 4))
    except (TypeError, ValueError):
        max_gap_rounds = 2
    enable_gap = opts.get("enable_gap_search")
    if enable_gap is None:
        enable_gap = cfg.get("enable_gap_search", True)
    return {
        "coverage_gap_threshold": coverage_threshold,
        "data_spec_gap_threshold": data_spec_threshold,
        "max_gap_rounds": max_gap_rounds,
        "enable_gap_search": bool(enable_gap),
    }


def build_gap_search_queries(
    coverage_report: Optional[Dict[str, Any]] = None,
    refinement_notes: Optional[List[str]] = None,
    data_requirements: Optional[Dict[str, Any]] = None,
    *,
    data_spec_coverage: Optional[Dict[str, Any]] = None,
) -> List[str]:
    queries: List[str] = []
    cov = coverage_report or {}
    req = data_requirements or {}
    spec_cov = data_spec_coverage or cov.get("data_spec_coverage") or {}

    for gap in cov.get("gaps") or []:
        if isinstance(gap, str) and gap.strip():
            queries.append(gap.strip()[:120])
    for gap in spec_cov.get("gaps") or []:
        if isinstance(gap, str) and gap.strip():
            queries.append(gap.strip()[:120])

    for field in (spec_cov.get("entities_miss") or [])[:3]:
        queries.append(f"dataset with column {field}"[:80])
    for field in (spec_cov.get("targets_miss") or [])[:3]:
        queries.append(f"benchmark metric {field}"[:80])

    for kw in (req.get("dataset_keywords") or [])[:4]:
        if kw:
            queries.append(str(kw)[:80])
    for kw in (req.get("domain_keywords") or [])[:3]:
        if kw:
            queries.append(str(kw)[:80])

    for note in (refinement_notes or [])[:3]:
        if note and len(note) > 8:
            queries.append(note[:100])

    dedup: List[str] = []
    seen = set()
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            dedup.append(q)
    return dedup[:8]


def should_run_gap_enrichment(
    coverage_report: Optional[Dict[str, Any]] = None,
    threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    *,
    data_spec_threshold: float = DEFAULT_DATA_SPEC_THRESHOLD,
) -> bool:
    cov = coverage_report or {}
    try:
        score = float(cov.get("completeness_score")) if cov.get("completeness_score") is not None else None
    except (TypeError, ValueError):
        score = None
    if score is None or score < threshold:
        return True

    spec_cov = cov.get("data_spec_coverage") or {}
    spec_score = spec_cov.get("data_spec_score")
    has_spec_fields = bool(
        spec_cov.get("entities_requested") or spec_cov.get("targets_requested")
    )
    if has_spec_fields and spec_score is not None:
        try:
            if float(spec_score) < data_spec_threshold:
                return True
        except (TypeError, ValueError):
            return True
    return False


def pick_import_candidates(
    external_candidates: List[Dict[str, Any]],
    *,
    max_count: int = 2,
) -> List[Dict[str, Any]]:
    from app.services.external_dataset_import_service import _rank_import_candidates

    return _rank_import_candidates(external_candidates)[:max_count]
