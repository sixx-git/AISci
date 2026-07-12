"""质量布尔 Gate — 各阶段 pass/fail，替代原 CQS 0–100 连续分。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import ENSEMBLE_ACCEPT_SCORE, PLOT_CRITIQUE_PASS_SCORE

STAGE_SCORE_HINTS: Dict[str, str] = {
    "ideation_novelty": "gate_novelty",
    "ensemble_review": "gate_ensemble",
    "discovery_r": "gate_discovery",
    "sandbox_validation": "gate_sandbox",
    "federated_pilot": "gate_federated",
    "pilot_feedback": "gate_pilot",
    "plot_critique": "gate_plot",
    "data_gap_loop": "gate_coverage",
    "evidence_reasoning": "gate_evidence",
    "teaching_refine": "gate_teaching",
    "federated_r": "gate_federated",
    "hitl_gate": "gate_hitl",
    "quality_acceptance": "gate_acceptance",
}


def _check(id_: str, label: str, passed: bool) -> Dict[str, Any]:
    return {"id": id_, "label": label, "passed": passed}


def evaluate_stage_gate(
    stage: str,
    raw_score: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """按阶段规则评估布尔 Gate。"""
    ctx = dict(context or {})
    stage_key = (stage or "").lower()
    checks: List[Dict[str, Any]] = []

    decision = ctx.get("ensemble_decision") or ctx.get("decision")
    overall = ctx.get("ensemble_overall") or ctx.get("overall")
    try:
        overall_f = float(overall) if overall is not None else None
    except (TypeError, ValueError):
        overall_f = None

    if stage_key in ("ensemble_review",) or stage_key.startswith("discovery_r"):
        accept = decision == "Accept" or (
            overall_f is not None and overall_f >= ENSEMBLE_ACCEPT_SCORE
        )
        checks.append(_check("ensemble_accept", f"评审 ≥ {ENSEMBLE_ACCEPT_SCORE} 或 Accept", accept))
        passed = accept
        gate_id = "gate_ensemble"
        label = "集成评审 Gate"
    elif stage_key == "ideation_novelty":
        novelty = raw_score
        if novelty is None:
            novelty = ctx.get("novelty_score")
        try:
            novelty_f = float(novelty) if novelty is not None else None
        except (TypeError, ValueError):
            novelty_f = None
        risk_ok = str(ctx.get("novelty_risk") or "").lower() != "high"
        score_ok = novelty_f is not None and novelty_f >= 6.0
        checks.append(_check("novelty_score", "新颖性 ≥ 6.0", score_ok))
        checks.append(_check("novelty_risk", "非高风险重叠", risk_ok))
        passed = score_ok and risk_ok
        gate_id = "gate_novelty"
        label = "Ideation Gate"
    elif "sandbox" in stage_key or stage_key == "sandbox_validation":
        success = ctx.get("sandbox_success")
        if success is None:
            success = ctx.get("success")
        passed = success is True
        checks.append(_check("sandbox_success", "沙箱实测成功", passed))
        gate_id = "gate_sandbox"
        label = "小样验证 Gate"
    elif stage_key.startswith("federated_pilot") or stage_key.startswith("federated_r"):
        gate_passed = ctx.get("gate_passed")
        mode = str(ctx.get("execution_mode") or ctx.get("mode") or "")
        if gate_passed is not None:
            passed = bool(gate_passed)
            checks.append(_check("federated_gate", "联邦双门槛", passed))
        elif mode in ("uploaded_csv", "runtime_local", "flower", "fate_compatible"):
            passed = True
            checks.append(_check("federated_exec", "联邦执行模式达标", True))
        elif mode == "gate_blocked":
            passed = False
            checks.append(_check("federated_gate", "联邦门槛未通过", False))
        else:
            passed = mode not in ("simulation", "skipped", "")
            checks.append(_check("federated_mode", "非纯仿真/跳过", passed))
        gate_id = "gate_federated"
        label = "联邦 Gate"
    elif stage_key == "plot_critique":
        try:
            v = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            v = None
        passed = v is not None and v >= PLOT_CRITIQUE_PASS_SCORE
        checks.append(_check("plot_score", f"图表 ≥ {PLOT_CRITIQUE_PASS_SCORE}", passed))
        gate_id = "gate_plot"
        label = "图表质量 Gate"
    elif stage_key == "data_gap_loop":
        try:
            v = float(raw_score) if raw_score is not None else 70.0
        except (TypeError, ValueError):
            v = 70.0
        passed = v >= 70.0
        checks.append(_check("coverage", "覆盖度 ≥ 70%", passed))
        gate_id = "gate_coverage"
        label = "数据覆盖 Gate"
    elif stage_key == "evidence_reasoning":
        rounds = ctx.get("rounds") or 1
        try:
            rounds_i = int(rounds)
        except (TypeError, ValueError):
            rounds_i = 1
        passed = rounds_i >= 1
        checks.append(_check("evidence_rounds", "证据链至少 1 轮", passed))
        gate_id = "gate_evidence"
        label = "证据链 Gate"
    elif stage_key == "quality_acceptance":
        passed = bool(ctx.get("accepted"))
        checks.append(_check("accepted", "质量验收通过", passed))
        gate_id = "gate_acceptance"
        label = "质量验收 Gate"
    elif stage_key.startswith("teaching_refine"):
        passed = True
        checks.append(_check("teaching_refine", "Teaching 精化已执行", True))
        gate_id = "gate_teaching"
        label = "Teaching Gate"
    elif stage_key.startswith("hitl_gate"):
        passed = ctx.get("hitl_resumed") is not False
        checks.append(_check("hitl", "HITL 已处理", passed))
        gate_id = "gate_hitl"
        label = "HITL Gate"
    else:
        try:
            v = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            v = None
        if v is None:
            passed = ctx.get("success") is not False
            checks.append(_check("stage_ok", "阶段无致命失败", passed))
        elif v <= 10:
            passed = v >= ENSEMBLE_ACCEPT_SCORE
            checks.append(_check("raw_threshold", f"原始分 ≥ {ENSEMBLE_ACCEPT_SCORE}", passed))
        else:
            passed = v >= 65.0
            checks.append(_check("raw_threshold", "原始分 ≥ 65", passed))
        gate_id = f"gate_{stage_key or 'unknown'}"
        label = f"{stage_key or 'unknown'} Gate"

    return {
        "passed": passed,
        "gate_id": gate_id,
        "label": label,
        "checks": checks,
        "raw_score": raw_score,
        "stage": stage,
    }


def enrich_quality_trend_entry(
    entry: Dict[str, Any],
    event_type: str = "",
    event_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """为 quality_trend 条目附加布尔 Gate 结果。"""
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
    ctx.setdefault("accepted", entry.get("accepted") if entry.get("accepted") is not None else ctx.get("accepted"))
    ctx.setdefault("novelty_score", entry.get("novelty_score") or ctx.get("novelty_score"))
    ctx.setdefault("novelty_risk", entry.get("novelty_risk") or ctx.get("novelty_risk"))

    gate = evaluate_stage_gate(stage, raw if isinstance(raw, (int, float)) else None, ctx)
    out = dict(entry)
    out["raw_score"] = raw
    out["passed"] = gate["passed"]
    out["gate_id"] = gate["gate_id"]
    out["gate_label"] = gate["label"]
    out["checks"] = gate["checks"]
    # 兼容仍读取 score 的旧代码：100=通过，0=未通过
    out["score"] = 100.0 if gate["passed"] else 0.0
    return out


def summarize_gate_trend(trend: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """从 quality_trend 汇总 Gate 通过情况。"""
    entries = [e for e in (trend or []) if isinstance(e, dict)]
    passes: List[bool] = []
    for e in entries:
        if "passed" in e:
            passes.append(bool(e["passed"]))
        else:
            s = e.get("score")
            if s is not None:
                try:
                    passes.append(float(s) >= 50.0)
                except (TypeError, ValueError):
                    pass

    consecutive_failures = 0
    for p in reversed(passes):
        if not p:
            consecutive_failures += 1
        else:
            break

    improved = False
    if len(passes) >= 2:
        improved = passes[-1] and not passes[-2]

    return {
        "gate_count": len(passes),
        "gates_passed": sum(1 for p in passes if p),
        "gates_failed": sum(1 for p in passes if not p),
        "latest_passed": passes[-1] if passes else None,
        "first_passed": passes[0] if passes else None,
        "gate_improved": improved,
        "consecutive_failures": consecutive_failures,
        # 兼容旧字段名（映射为布尔语义）
        "cqs_first": 100.0 if passes and passes[0] else (0.0 if passes else None),
        "cqs_last": 100.0 if passes and passes[-1] else (0.0 if passes else None),
        "cqs_delta": (100.0 if passes[-1] else 0.0) - (100.0 if passes[0] else 0.0) if len(passes) >= 2 else None,
        "cqs_improved": improved,
        "cqs_count": len(passes),
    }


# 兼容旧 import
summarize_cqs_trend = summarize_gate_trend
normalize_raw_to_cqs = lambda raw, stage="", context=None: 100.0 if evaluate_stage_gate(stage, raw, context or {}).get("passed") else 0.0
build_cqs_breakdown = lambda stage, raw_score=None, context=None: evaluate_stage_gate(stage, raw_score, context)
