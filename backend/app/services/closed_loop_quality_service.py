"""闭环质量验收 — 基于布尔 Gate 分析 quality_trend 与迭代成效"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import ENSEMBLE_ACCEPT_SCORE
from app.core.quality_scoring import summarize_gate_trend


def compute_quality_acceptance(
    quality_trend: Optional[List[Dict[str, Any]]] = None,
    closed_loop_events: Optional[List[Dict[str, Any]]] = None,
    discovery_loop: Optional[Dict[str, Any]] = None,
    hypothesis_review: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """汇总闭环 Gate 通过情况、Accept 状态与薄弱环节。"""
    trend = list(quality_trend or [])
    events = list(closed_loop_events or [])
    gate_summary = summarize_gate_trend(trend)

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

    failed_stages: List[str] = []
    for entry in trend:
        if not isinstance(entry, dict):
            continue
        passed = entry.get("passed")
        if passed is None:
            s = entry.get("score")
            if s is not None:
                try:
                    passed = float(s) >= 50.0
                except (TypeError, ValueError):
                    passed = None
        if passed is False:
            failed_stages.append(str(entry.get("gate_label") or entry.get("stage") or entry.get("label") or "unknown"))

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

    gates_passed = int(gate_summary.get("gates_passed") or 0)
    gates_failed = int(gate_summary.get("gates_failed") or 0)
    latest_passed = gate_summary.get("latest_passed")
    gate_improved = gate_summary.get("gate_improved")

    # 数值分改善：兼容 0–10 ensemble / 未归一化的 trend score（Gate 阈值 50 下两者可能都未通过）
    numeric_scores: List[float] = []
    for entry in trend:
        if not isinstance(entry, dict) or entry.get("score") is None:
            continue
        try:
            numeric_scores.append(float(entry["score"]))
        except (TypeError, ValueError):
            continue
    numeric_improved = (
        len(numeric_scores) >= 2 and numeric_scores[-1] > numeric_scores[0]
    )

    verdict = "pass"
    if not accepted:
        verdict = "needs_review"
    if sandbox_success is False:
        verdict = "needs_review"
    if gates_failed > 0 and gates_passed == 0 and not accepted:
        verdict = "stagnant"
    elif gates_failed >= 2 and latest_passed is False and not accepted:
        verdict = "stagnant"

    summary_parts = []
    if accepted:
        summary_parts.append("集成评审已 Accept")
    else:
        summary_parts.append(f"集成评审未 Accept（decision={decision or '—'}）")
    if gate_summary.get("gate_count", 0) > 0:
        summary_parts.append(f"质量 Gate {gates_passed} 通过 / {gates_failed} 未通过")
        if latest_passed is not None:
            summary_parts.append(f"最近 Gate {'通过' if latest_passed else '未通过'}")
        if gate_improved:
            summary_parts.append("较上轮 Gate 改善")
    if discovery_rounds > 1:
        summary_parts.append(f"Discovery 执行 {discovery_rounds} 轮")
    if fed_discovery_accept:
        summary_parts.append("Discovery 联邦双门槛已通过")
    if literature_refreshes:
        summary_parts.append(f"文献刷新 {literature_refreshes} 次")
    if failed_stages:
        summary_parts.append(f"未通过: {', '.join(list(dict.fromkeys(failed_stages))[:4])}")

    return {
        "verdict": verdict,
        "accepted": accepted,
        "ensemble_decision": decision,
        "ensemble_overall": overall_f,
        "gates_passed": gates_passed,
        "gates_failed": gates_failed,
        "latest_gate_passed": latest_passed,
        "gate_improved": gate_improved,
        "failed_gates": list(dict.fromkeys(failed_stages)),
        "score_improved": bool(gate_improved) or numeric_improved,
        "score_delta": (
            (numeric_scores[-1] - numeric_scores[0])
            if len(numeric_scores) >= 2
            else gate_summary.get("cqs_delta")
        ),
        "first_score": numeric_scores[0] if numeric_scores else gate_summary.get("cqs_first"),
        "last_score": numeric_scores[-1] if numeric_scores else gate_summary.get("cqs_last"),
        "weak_stages": list(dict.fromkeys(failed_stages)),
        "sandbox_success": sandbox_success,
        "discovery_rounds": discovery_rounds,
        "literature_refresh_count": literature_refreshes,
        "refining_rounds": len([h for h in discovery_history if h.get("status") == "refining"]),
        "federated_discovery_accept": fed_discovery_accept,
        "cqs_first": gate_summary.get("cqs_first"),
        "cqs_last": gate_summary.get("cqs_last"),
        "cqs_delta": gate_summary.get("cqs_delta"),
        "cqs_improved": bool(gate_improved) or numeric_improved,
        "summary": "；".join(summary_parts),
    }


def get_closed_loop_quality_service():
    return compute_quality_acceptance
