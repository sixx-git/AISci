"""Loop 决策 Dry-run — 不调 LLM，仅模拟停滞/验收判断。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import resolve_run_options
from app.services.loops.discovery_runner import (
    check_discovery_acceptance,
    check_discovery_stagnation,
)


def simulate_loop_decisions(
    *,
    run_options: Optional[Dict[str, Any]] = None,
    quality_trend: Optional[List[Dict[str, Any]]] = None,
    round_num: int = 2,
    hypothesis_review: Optional[Dict[str, Any]] = None,
    small_validation: Optional[Dict[str, Any]] = None,
    project_mode: str = "standard",
) -> Dict[str, Any]:
    opts = resolve_run_options(run_options)
    mode = opts.get("pipeline_mode", "teaching")
    trend = list(quality_trend or [])

    out: Dict[str, Any] = {
        "resolved_options": opts,
        "iteration_mode": opts.get("iteration_mode"),
        "pipeline_mode": mode,
        "round_num": round_num,
    }

    if mode == "discovery":
        stagnant_rounds = int(opts.get("gate_stagnant_rounds") or 2)
        stagnation = check_discovery_stagnation(
            trend,
            round_num=round_num,
            stagnant_rounds=max(1, min(stagnant_rounds, 4)),
        )
        out["discovery_stagnation"] = stagnation
        if hypothesis_review is not None:
            accepted, meta = check_discovery_acceptance(
                hypothesis_review,
                small_validation or {},
                project_mode=project_mode,
            )
            out["discovery_acceptance"] = {"accepted": accepted, **meta}

    gap_thresholds = {
        "coverage_gap_threshold": opts.get("coverage_gap_threshold"),
        "data_spec_gap_threshold": opts.get("data_spec_gap_threshold"),
        "max_gap_rounds": opts.get("max_gap_rounds"),
        "enable_gap_search": opts.get("enable_gap_search"),
    }
    out["gap_loop_config"] = gap_thresholds

    teaching_flags = {
        "enable_hitl_gate": opts.get("enable_hitl_gate"),
        "hitl_gate_stages": opts.get("hitl_gate_stages"),
        "enable_teaching_auto_refinement": opts.get("enable_teaching_auto_refinement"),
    }
    out["teaching_config"] = teaching_flags

    # 可读摘要
    lines: List[str] = [f"迭代模式: {opts.get('iteration_mode', mode)}"]
    if mode == "discovery" and "discovery_stagnation" in out:
        st = out["discovery_stagnation"]
        lines.append(f"Discovery 停滞判断: {st.get('action')} — {st.get('reason')}")
    if opts.get("enable_gap_search"):
        lines.append(
            f"Gap 补搜: 覆盖率阈值 {gap_thresholds['coverage_gap_threshold']}%, "
            f"最多 {gap_thresholds['max_gap_rounds']} 轮"
        )
    if mode == "teaching" and opts.get("enable_hitl_gate"):
        lines.append(f"HITL Gate: 开启 ({len(opts.get('hitl_gate_stages') or [])} 个阶段)")
    out["summary"] = " · ".join(lines)

    return out
