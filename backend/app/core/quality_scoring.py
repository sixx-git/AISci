"""综合质量评分 CQS — 将各阶段原始分统一归一化到 0–100"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import ENSEMBLE_ACCEPT_SCORE

# 阶段 → 原始分量纲说明
STAGE_SCORE_HINTS: Dict[str, str] = {
    "ideation_novelty": "0_10",
    "ensemble_review": "0_10",
    "discovery_r": "0_10",
    "sandbox_validation": "binary_10",
    "federated_pilot": "mode_weighted",
    "pilot_feedback": "0_10",
    "plot_critique": "0_10",
    "teaching_refine": "fixed",
    "federated_r": "fixed",
    "hitl_gate": "fixed",
}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def normalize_raw_to_cqs(raw: Optional[float], stage: str = "", context: Optional[Dict[str, Any]] = None) -> float:
    """将各阶段原始分映射为 0–100 CQS。"""
    ctx = context or {}
    stage_key = (stage or "").lower()

    if raw is None:
        if ctx.get("success") is True:
            return 85.0
        if ctx.get("success") is False:
            return 35.0
        return 50.0

    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 50.0

    if "sandbox" in stage_key or stage_key == "sandbox_validation":
        return 88.0 if v >= 7 else (38.0 if v <= 4 else _clamp(v * 10))

    if stage_key.startswith("federated_pilot") or stage_key.startswith("federated_r"):
        mode = str(ctx.get("execution_mode") or ctx.get("mode") or "")
        if mode == "uploaded_csv":
            return 90.0
        if mode in ("runtime_local", "flower", "fate_compatible"):
            return 82.0
        if mode == "gate_blocked":
            return 30.0
        if mode == "simulation":
            return 55.0
        if mode == "skipped":
            return 45.0
        return _clamp(v * 10 if v <= 10 else v)

    if stage_key.startswith("teaching_refine"):
        return 62.0

    if stage_key.startswith("hitl_gate"):
        return 60.0

    # 默认 0–10 量纲（ensemble、ideation、discovery）
    if v <= 10:
        return _clamp(v * 10)
    return _clamp(v)


def build_cqs_breakdown(
    stage: str,
    raw_score: Optional[float],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = dict(context or {})
    cqs = normalize_raw_to_cqs(raw_score, stage, ctx)
    components: Dict[str, float] = {"base": round(cqs, 1)}

    if ctx.get("ensemble_decision") == "Accept" or (
        ctx.get("ensemble_overall") is not None
        and float(ctx["ensemble_overall"]) >= ENSEMBLE_ACCEPT_SCORE
    ):
        components["ensemble_bonus"] = 5.0
        cqs = _clamp(cqs + 5.0)

    if ctx.get("sandbox_success") is True:
        components["sandbox_bonus"] = 8.0
        cqs = _clamp(cqs + 8.0)
    elif ctx.get("sandbox_success") is False:
        components["sandbox_penalty"] = -15.0
        cqs = _clamp(cqs - 15.0)

    if ctx.get("gate_passed") is True:
        components["federated_gate_bonus"] = 6.0
        cqs = _clamp(cqs + 6.0)
    elif ctx.get("gate_passed") is False:
        components["federated_gate_penalty"] = -20.0
        cqs = _clamp(cqs - 20.0)

    return {
        "cqs": round(cqs, 1),
        "raw_score": raw_score,
        "stage": stage,
        "scale": STAGE_SCORE_HINTS.get(stage.split("_r")[0], "0_10"),
        "components": components,
    }


def enrich_quality_trend_entry(
    entry: Dict[str, Any],
    event_type: str = "",
    event_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """为 quality_trend 条目附加 CQS（0–100）并更新 score 字段。"""
    if not isinstance(entry, dict):
        return entry
    stage = str(entry.get("stage") or entry.get("label") or event_type or "unknown")
    raw = entry.get("raw_score", entry.get("score"))
    ctx = dict(event_payload or {})
    ctx.setdefault("success", entry.get("success"))
    ctx.setdefault("execution_mode", entry.get("execution_mode") or ctx.get("execution_mode"))
    ctx.setdefault("ensemble_decision", entry.get("decision") or ctx.get("decision"))
    ctx.setdefault("ensemble_overall", entry.get("overall") or ctx.get("overall"))
    ctx.setdefault("sandbox_success", entry.get("success") if "sandbox" in stage else ctx.get("sandbox_success"))
    ctx.setdefault("gate_passed", entry.get("gate_passed") if entry.get("gate_passed") is not None else ctx.get("gate_passed"))

    breakdown = build_cqs_breakdown(stage, raw if isinstance(raw, (int, float)) else None, ctx)
    out = dict(entry)
    out["raw_score"] = raw
    out["cqs"] = breakdown["cqs"]
    out["score"] = breakdown["cqs"]
    out["breakdown"] = breakdown.get("components")
    return out


def summarize_cqs_trend(trend: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """从 quality_trend 汇总 CQS 首尾变化。"""
    entries = list(trend or [])
    scores = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        s = e.get("cqs", e.get("score"))
        if s is not None:
            try:
                scores.append(float(s))
            except (TypeError, ValueError):
                pass

    improved = False
    delta = None
    if len(scores) >= 2:
        delta = round(scores[-1] - scores[0], 1)
        improved = scores[-1] > scores[0]

    return {
        "cqs_first": scores[0] if scores else None,
        "cqs_last": scores[-1] if scores else None,
        "cqs_delta": delta,
        "cqs_improved": improved,
        "cqs_count": len(scores),
    }
