"""Pipeline 运行模式 — Teaching（HITL） vs Discovery（Sakana-like 开放循环）"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class PipelineMode(str, Enum):
    TEACHING = "teaching"
    DISCOVERY = "discovery"


VALID_PIPELINE_MODES = {PipelineMode.TEACHING.value, PipelineMode.DISCOVERY.value}

DEFAULT_NUM_IDEAS = 3
DEFAULT_DISCOVERY_MAX_ROUNDS = 3
DEFAULT_TEACHING_AUTO_REFINEMENT_MAX = 1
DEFAULT_FEDERATED_CAMPAIGN_MAX = 2
DEFAULT_HITL_GATE_STAGES = (
    "hypothesis_generation",
    "hypothesis_review",
    "experiment_design",
    "small_validation",
    "report_generation",
)
DEFAULT_MIN_IMPROVEMENT_DELTA = 3.0
DEFAULT_COVERAGE_GAP_THRESHOLD = 70.0
DEFAULT_DATA_SPEC_GAP_THRESHOLD = 60.0
DEFAULT_MAX_GAP_ROUNDS = 2
DEFAULT_CON_CHALLENGE_MAX_ROUNDS = 2
PLOT_CRITIQUE_PASS_SCORE = 6.5
ENSEMBLE_ACCEPT_SCORE = 6.5
VALID_ADVERSARIAL_MODES = ("single_group", "multi_group", "off")

HITL_GATE_STAGE_LABELS = {
    "hypothesis_generation": "假设生成",
    "hypothesis_review": "假设评审",
    "experiment_design": "实验设计",
    "small_validation": "小样验证",
    "report_generation": "报告生成",
}


def normalize_pipeline_mode(mode: str | None) -> str:
    if mode and mode in VALID_PIPELINE_MODES:
        return mode
    return PipelineMode.TEACHING.value


PIPELINE_MODE_LABELS_ZH = {
    PipelineMode.TEACHING.value: "Teaching 模式 — 单轮自动精化，适合研究生仿真",
    PipelineMode.DISCOVERY.value: "Discovery 模式 — Sakana-like 自动 ideate→experiment→review 循环",
}


def resolve_run_options(options: Dict[str, Any] | None) -> Dict[str, Any]:
    opts = dict(options or {})
    mode = normalize_pipeline_mode(opts.get("pipeline_mode"))
    num_ideas = opts.get("num_ideas", DEFAULT_NUM_IDEAS)
    try:
        num_ideas = max(1, min(int(num_ideas), 8))
    except (TypeError, ValueError):
        num_ideas = DEFAULT_NUM_IDEAS
    max_rounds = opts.get("discovery_max_rounds", DEFAULT_DISCOVERY_MAX_ROUNDS)
    try:
        max_rounds = max(1, min(int(max_rounds), 5))
    except (TypeError, ValueError):
        max_rounds = DEFAULT_DISCOVERY_MAX_ROUNDS
    teaching_auto = opts.get("enable_teaching_auto_refinement")
    if teaching_auto is None:
        teaching_auto = mode == PipelineMode.TEACHING.value
    try:
        fed_max = int(opts.get("federated_campaign_max", DEFAULT_FEDERATED_CAMPAIGN_MAX))
        fed_max = max(1, min(fed_max, 3))
    except (TypeError, ValueError):
        fed_max = DEFAULT_FEDERATED_CAMPAIGN_MAX
    enable_hitl_gate = opts.get("enable_hitl_gate")
    if enable_hitl_gate is None:
        enable_hitl_gate = False
    gate_stages = opts.get("hitl_gate_stages")
    if not gate_stages:
        gate_stages = list(DEFAULT_HITL_GATE_STAGES)
    min_delta = opts.get("min_improvement_delta", DEFAULT_MIN_IMPROVEMENT_DELTA)
    try:
        min_delta = float(min_delta)
    except (TypeError, ValueError):
        min_delta = DEFAULT_MIN_IMPROVEMENT_DELTA
    coverage_threshold = opts.get("coverage_gap_threshold", DEFAULT_COVERAGE_GAP_THRESHOLD)
    try:
        coverage_threshold = float(coverage_threshold)
    except (TypeError, ValueError):
        coverage_threshold = DEFAULT_COVERAGE_GAP_THRESHOLD
    data_spec_threshold = opts.get("data_spec_gap_threshold", DEFAULT_DATA_SPEC_GAP_THRESHOLD)
    try:
        data_spec_threshold = float(data_spec_threshold)
    except (TypeError, ValueError):
        data_spec_threshold = DEFAULT_DATA_SPEC_GAP_THRESHOLD
    max_gap_rounds = opts.get("max_gap_rounds", DEFAULT_MAX_GAP_ROUNDS)
    try:
        max_gap_rounds = max(1, min(int(max_gap_rounds), 4))
    except (TypeError, ValueError):
        max_gap_rounds = DEFAULT_MAX_GAP_ROUNDS
    enable_quick_report = bool(opts.get("enable_quick_report"))
    if enable_quick_report:
        mode = PipelineMode.DISCOVERY.value
        enable_hitl_gate = False
        teaching_auto = False
    enable_pro_con = opts.get("enable_pro_con_adversarial", True)
    adversarial_mode = opts.get("adversarial_mode", "single_group")
    if adversarial_mode not in VALID_ADVERSARIAL_MODES:
        adversarial_mode = "single_group"
    if not enable_pro_con:
        adversarial_mode = "off"
    if adversarial_mode == "multi_group" and num_ideas < 2:
        adversarial_mode = "single_group"
    con_max_rounds = opts.get("con_challenge_max_rounds", DEFAULT_CON_CHALLENGE_MAX_ROUNDS)
    try:
        con_max_rounds = max(1, min(int(con_max_rounds), 4))
    except (TypeError, ValueError):
        con_max_rounds = DEFAULT_CON_CHALLENGE_MAX_ROUNDS
    return {
        "pipeline_mode": mode,
        "num_ideas": num_ideas,
        "discovery_max_rounds": max_rounds,
        "force_sandbox": mode == PipelineMode.DISCOVERY.value or bool(opts.get("force_sandbox")),
        "enable_plot_vlm_critique": opts.get("enable_plot_vlm_critique", True),
        "enable_teaching_auto_refinement": bool(teaching_auto),
        "teaching_auto_refinement_max": DEFAULT_TEACHING_AUTO_REFINEMENT_MAX,
        "enable_federated_campaign_loop": bool(opts.get("enable_federated_campaign_loop", True)),
        "federated_campaign_max": fed_max,
        "sandbox_use_docker": bool(opts.get("sandbox_use_docker")),
        "enable_hitl_gate": bool(enable_hitl_gate),
        "hitl_gate_stages": list(gate_stages),
        "enable_executability_gate": opts.get("enable_executability_gate", True),
        "min_improvement_delta": min_delta,
        "enable_gap_search": opts.get("enable_gap_search", True),
        "enable_hf_auto_import": opts.get("enable_hf_auto_import", True),
        "coverage_gap_threshold": coverage_threshold,
        "data_spec_gap_threshold": data_spec_threshold,
        "max_gap_rounds": max_gap_rounds,
        "enable_quick_report": enable_quick_report,
        "enable_pro_con_adversarial": bool(enable_pro_con),
        "adversarial_mode": adversarial_mode,
        "con_challenge_max_rounds": con_max_rounds,
        "enable_hypothesis_evolution": bool(opts.get("enable_hypothesis_evolution", True)),
    }
