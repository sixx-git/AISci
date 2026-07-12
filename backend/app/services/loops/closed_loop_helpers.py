"""闭环事件与质量 Gate 趋势条目构建辅助。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def summarize_gap_loop(gap_loop: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    items = list(gap_loop or [])
    executed = [r for r in items if isinstance(r, dict) and not r.get("skipped")]
    score_before: Optional[float] = None
    score_after: Optional[float] = None
    imported_total = 0

    for row in items:
        if not isinstance(row, dict):
            continue
        if row.get("score_before") is not None:
            try:
                score_before = float(row["score_before"])
            except (TypeError, ValueError):
                pass
        if row.get("score_after") is not None:
            try:
                score_after = float(row["score_after"])
            except (TypeError, ValueError):
                pass
        import_meta = row.get("import_meta") or {}
        if isinstance(import_meta, dict):
            try:
                imported_total += int(import_meta.get("imported_count") or 0)
            except (TypeError, ValueError):
                pass

    summary_parts = [f"Gap 补搜 {len(executed)} 轮"]
    if score_before is not None and score_after is not None:
        summary_parts.append(f"覆盖率 {score_before:.0f}→{score_after:.0f}")
    if imported_total:
        summary_parts.append(f"导入 {imported_total} 项")

    return {
        "rounds": len(items),
        "executed_rounds": len(executed),
        "score_before": score_before,
        "score_after": score_after,
        "imported_count": imported_total,
        "summary": " · ".join(summary_parts),
        "gap_loop": items[:12],
    }


def build_data_gap_loop_payload(
    gap_loop: Optional[List[Dict[str, Any]]],
    gap_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    summary = summarize_gap_loop(gap_loop)
    payload: Dict[str, Any] = {
        **summary,
        "gap_enrichment": gap_meta or {},
    }
    score_after = summary.get("score_after")
    if score_after is not None:
        payload["quality_trend_entry"] = {
            "stage": "data_gap_loop",
            "score": score_after,
            "raw_score": score_after,
            "label": "Gap 补搜",
        }
    return payload


def infer_quality_trend_entries(event_type: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从事件 payload 推断 quality_trend 条目（统一 Gate enrich 入口）。"""
    qt = payload.get("quality_trend_entry") or payload.get("quality_trend")
    if isinstance(qt, dict) and qt.get("stage"):
        return [qt]
    if isinstance(qt, list):
        return [item for item in qt if isinstance(item, dict) and item.get("stage")]

    inferred: List[Dict[str, Any]] = []
    overall = payload.get("overall")
    if overall is not None:
        inferred.append({
            "stage": str(payload.get("stage") or event_type),
            "score": overall,
            "round": payload.get("round"),
        })
        return inferred

    if event_type == "data_gap_loop" and payload.get("score_after") is not None:
        inferred.append({
            "stage": "data_gap_loop",
            "score": payload["score_after"],
            "raw_score": payload["score_after"],
            "label": "Gap 补搜",
        })
        return inferred

    if event_type == "evidence_reasoning_loop" and payload.get("rounds"):
        try:
            rounds = int(payload["rounds"])
        except (TypeError, ValueError):
            rounds = 1
        inferred.append({
            "stage": "evidence_reasoning",
            "score": min(9.0, 6.0 + rounds * 1.2),
            "label": "证据迭代",
            "round": rounds,
        })
        return inferred

    if event_type == "quality_acceptance":
        accepted = payload.get("accepted")
        if accepted is not None:
            inferred.append({
                "stage": "quality_acceptance",
                "score": 8.5 if accepted else 4.5,
                "label": "质量验收",
            })
    return inferred
