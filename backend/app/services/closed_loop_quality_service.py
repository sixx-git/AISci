"""闭环质量验收 — 分析 quality_trend 与迭代成效"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import ENSEMBLE_ACCEPT_SCORE


def compute_quality_acceptance(
    quality_trend: Optional[List[Dict[str, Any]]] = None,
    closed_loop_events: Optional[List[Dict[str, Any]]] = None,
    discovery_loop: Optional[Dict[str, Any]] = None,
    hypothesis_review: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """汇总闭环是否 Accept、分数是否提升、薄弱环节。"""
    trend = list(quality_trend or [])
    events = list(closed_loop_events or [])
    scores = [float(t["score"]) for t in trend if t.get("score") is not None]

    hr = hypothesis_review or {}
    ensemble = (hr.get("skill_outputs") or {}).get("ensemble_review") or {}
    decision = ensemble.get("decision") or hr.get("ensemble_decision")
    overall = ensemble.get("overall") or hr.get("ensemble_overall")
    try:
        overall_f = float(overall) if overall is not None else None
    except (TypeError, ValueError):
        overall_f = None

    accepted = decision == "Accept" or (
        overall_f is not None and overall_f >= ENSEMBLE_ACCEPT_SCORE
    )

    improved = False
    delta = None
    if len(scores) >= 2:
        delta = round(scores[-1] - scores[0], 2)
        improved = scores[-1] > scores[0]

    weak_stages: List[str] = []
    if trend:
        avg = sum(scores) / len(scores) if scores else 0
        for entry in trend:
            s = entry.get("score")
            if s is None:
                continue
            if float(s) < avg * 0.85:
                weak_stages.append(str(entry.get("stage") or entry.get("label") or "unknown"))

    sandbox_events = [e for e in events if e.get("type") == "sandbox_validation"]
    sandbox_success = any(e.get("success") for e in sandbox_events) if sandbox_events else None

    discovery_rounds = (discovery_loop or {}).get("rounds_executed") or 0
    discovery_history = (discovery_loop or {}).get("history") or []
    fed_discovery_accept = any(
        h.get("federated_acceptance", {}).get("accepted") for h in discovery_history if isinstance(h, dict)
    )
    literature_refreshes = sum(
        1 for e in events if e.get("type") == "discovery_literature_refresh"
    )

    verdict = "pass"
    if not accepted:
        verdict = "needs_review"
    if sandbox_success is False:
        verdict = "needs_review"
    if len(scores) >= 2 and not improved and not accepted:
        verdict = "stagnant"

    summary_parts = []
    if accepted:
        summary_parts.append("集成评审已 Accept")
    else:
        summary_parts.append(f"集成评审未 Accept（decision={decision or '—'}）")
    if delta is not None:
        summary_parts.append(f"质量趋势 {'↑' if improved else '→/↓'} {delta:+.1f}")
    if discovery_rounds > 1:
        summary_parts.append(f"Discovery 执行 {discovery_rounds} 轮")
    if fed_discovery_accept:
        summary_parts.append("Discovery 联邦双门槛已通过")
    if literature_refreshes:
        summary_parts.append(f"文献刷新 {literature_refreshes} 次")
    if weak_stages:
        summary_parts.append(f"薄弱阶段: {', '.join(dict.fromkeys(weak_stages)[:4])}")

    return {
        "verdict": verdict,
        "accepted": accepted,
        "ensemble_decision": decision,
        "ensemble_overall": overall_f,
        "score_improved": improved,
        "score_delta": delta,
        "first_score": scores[0] if scores else None,
        "last_score": scores[-1] if scores else None,
        "weak_stages": list(dict.fromkeys(weak_stages)),
        "sandbox_success": sandbox_success,
        "discovery_rounds": discovery_rounds,
        "literature_refresh_count": literature_refreshes,
        "refining_rounds": len([h for h in discovery_history if h.get("status") == "refining"]),
        "federated_discovery_accept": fed_discovery_accept,
        "summary": "；".join(summary_parts),
    }


def get_closed_loop_quality_service():
    return compute_quality_acceptance
