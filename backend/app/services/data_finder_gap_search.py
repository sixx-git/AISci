"""Gap 驱动的外部数据补搜"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_COVERAGE_THRESHOLD = 70.0


def build_gap_search_queries(
    coverage_report: Optional[Dict[str, Any]] = None,
    refinement_notes: Optional[List[str]] = None,
    data_requirements: Optional[Dict[str, Any]] = None,
) -> List[str]:
    queries: List[str] = []
    cov = coverage_report or {}
    req = data_requirements or {}

    for gap in cov.get("gaps") or []:
        if isinstance(gap, str) and gap.strip():
            queries.append(gap.strip()[:120])

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
) -> bool:
    cov = coverage_report or {}
    score = cov.get("completeness_score")
    if score is None:
        return True
    try:
        return float(score) < threshold
    except (TypeError, ValueError):
        return True


def pick_import_candidates(
    external_candidates: List[Dict[str, Any]],
    *,
    max_count: int = 2,
) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for c in external_candidates or []:
        platform = (c.get("source_platform") or "").lower()
        score = float(c.get("confidence") or 0.5)
        if "huggingface" in platform:
            score += 0.2
        if c.get("imported"):
            continue
        ranked.append({**c, "_rank": score})
    ranked.sort(key=lambda x: x.get("_rank", 0), reverse=True)
    return [{k: v for k, v in c.items() if k != "_rank"} for c in ranked[:max_count]]
