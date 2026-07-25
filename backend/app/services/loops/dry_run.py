"""Loop 决策 Dry-run — 不调 LLM；人工主导模式下仅回显已解析的 run_options。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import resolve_run_options


def simulate_loop_decisions(
    *,
    run_options: Optional[Dict[str, Any]] = None,
    quality_trend: Optional[List[Dict[str, Any]]] = None,
    round_num: int = 2,
    hypothesis_review: Optional[Dict[str, Any]] = None,
    small_validation: Optional[Dict[str, Any]] = None,
    project_mode: str = "standard",
) -> Dict[str, Any]:
    del quality_trend, round_num, hypothesis_review, small_validation, project_mode  # 兼容旧 API 签名
    opts = resolve_run_options(run_options)

    out: Dict[str, Any] = {
        "resolved_options": opts,
        "iteration_mode": "human",
        "pipeline_mode": opts.get("pipeline_mode", "teaching"),
        "teaching_config": {
            "enable_hitl_gate": opts.get("enable_hitl_gate"),
            "hitl_gate_stages": opts.get("hitl_gate_stages"),
            "enable_teaching_auto_refinement": False,
        },
        "gap_loop_config": {
            "coverage_gap_threshold": opts.get("coverage_gap_threshold"),
            "data_spec_gap_threshold": opts.get("data_spec_gap_threshold"),
            "max_gap_rounds": opts.get("max_gap_rounds"),
            "enable_gap_search": opts.get("enable_gap_search"),
        },
        "summary": "迭代模式: human（人工主导；轻量自动 / Discovery 循环已退役）",
    }
    return out
