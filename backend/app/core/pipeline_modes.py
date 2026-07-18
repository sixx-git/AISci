"""Pipeline 运行模式 — 迭代模式（human / teaching_auto / discovery_auto）与底层执行参数"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class PipelineMode(str, Enum):
    TEACHING = "teaching"
    DISCOVERY = "discovery"


class IterationMode(str, Enum):
    HUMAN = "human"
    TEACHING_AUTO = "teaching_auto"
    DISCOVERY_AUTO = "discovery_auto"


VALID_PIPELINE_MODES = {PipelineMode.TEACHING.value, PipelineMode.DISCOVERY.value}
VALID_ITERATION_MODES = {
    IterationMode.HUMAN.value,
    IterationMode.TEACHING_AUTO.value,
    IterationMode.DISCOVERY_AUTO.value,
}

DEFAULT_NUM_IDEAS = 3
DEFAULT_DISCOVERY_MAX_ROUNDS = 3
DEFAULT_TEACHING_AUTO_REFINEMENT_MAX = 1
DEFAULT_EXPERIMENT_SELF_CORRECTION_MAX = 2
DEFAULT_ITERATION_MODE = IterationMode.HUMAN.value
# 可行性评估后默认暂停：迭代实验 / 报告改由「迭代实验」页人工完成
DEFAULT_PAUSE_AFTER_HYPOTHESIS_REVIEW = True
# 其它 HITL 阶段门控仍默认关闭（假设生成等）
DEFAULT_HITL_GATE_STAGES: tuple[str, ...] = ()
DEFAULT_GATE_STAGNANT_ROUNDS = 2
DEFAULT_COVERAGE_GAP_THRESHOLD = 70.0
DEFAULT_DATA_SPEC_GAP_THRESHOLD = 60.0
DEFAULT_MAX_GAP_ROUNDS = 2
DEFAULT_CON_CHALLENGE_MAX_ROUNDS = 2
DEFAULT_LITERATURE_MAX_PAPERS = 10
DEFAULT_EVIDENCE_REASONING_MAX_ROUNDS = 1
PLOT_CRITIQUE_PASS_SCORE = 6.5
ENSEMBLE_ACCEPT_SCORE = 6.5
VALID_ADVERSARIAL_MODES = ("single_group", "multi_group", "off")

HITL_GATE_STAGE_LABELS = {
    "hypothesis_generation": "假设生成",
    "hypothesis_review": "假设评审",
    "iterative_experiment": "迭代实验",
    "report_generation": "报告生成",
}

ITERATION_MODE_LABELS_ZH = {
    IterationMode.HUMAN.value: "人工主导 — 单阶段重跑（假设/迭代实验页内审阅）",
    IterationMode.TEACHING_AUTO.value: "轻量自动 — 验证失败时自动精化 1 轮",
    IterationMode.DISCOVERY_AUTO.value: "深度自动 — 未 Accept 时多轮 Discovery 循环",
}

PIPELINE_MODE_LABELS_ZH = {
    PipelineMode.TEACHING.value: "Teaching 模式 — 单轮自动精化，适合研究生仿真",
    PipelineMode.DISCOVERY.value: "Discovery 模式 — Sakana-like 自动 ideate→experiment→review 循环",
}


def normalize_pipeline_mode(mode: str | None) -> str:
    if mode and mode in VALID_PIPELINE_MODES:
        return mode
    return PipelineMode.TEACHING.value


def resolve_iteration_mode(opts: Dict[str, Any]) -> str:
    """解析互斥的宏迭代模式；兼容旧版 pipeline_mode / enable_* 字段。"""
    explicit = opts.get("iteration_mode")
    if explicit in VALID_ITERATION_MODES:
        return str(explicit)

    legacy_mode = normalize_pipeline_mode(opts.get("pipeline_mode"))
    if legacy_mode == PipelineMode.DISCOVERY.value:
        return IterationMode.DISCOVERY_AUTO.value

    if opts.get("enable_hitl_gate"):
        return IterationMode.HUMAN.value

    teaching_auto = opts.get("enable_teaching_auto_refinement")
    if teaching_auto is None:
        # 旧默认是 teaching 下开启自动精化；新默认改为人工主导
        return DEFAULT_ITERATION_MODE
    if teaching_auto:
        return IterationMode.TEACHING_AUTO.value

    return DEFAULT_ITERATION_MODE


def apply_iteration_mode(opts: Dict[str, Any]) -> Dict[str, Any]:
    """将 iteration_mode 映射为互斥的 pipeline_mode / HITL / Teaching 精化开关。"""
    mode = resolve_iteration_mode(opts)
    out = dict(opts)
    out["iteration_mode"] = mode

    if mode == IterationMode.HUMAN.value:
        out["pipeline_mode"] = PipelineMode.TEACHING.value
        # HITL 阶段门控默认关闭（人工审在假设页 / 迭代实验页完成）
        out["enable_hitl_gate"] = bool(opts.get("enable_hitl_gate", False))
        out["enable_teaching_auto_refinement"] = False
    elif mode == IterationMode.TEACHING_AUTO.value:
        out["pipeline_mode"] = PipelineMode.TEACHING.value
        out["enable_hitl_gate"] = False
        out["enable_teaching_auto_refinement"] = True
    else:
        out["pipeline_mode"] = PipelineMode.DISCOVERY.value
        out["enable_hitl_gate"] = False
        out["enable_teaching_auto_refinement"] = False

    return out


def resolve_run_options(options: Dict[str, Any] | None) -> Dict[str, Any]:
    opts = apply_iteration_mode(dict(options or {}))
    mode = normalize_pipeline_mode(opts.get("pipeline_mode"))
    iteration_mode = opts.get("iteration_mode", DEFAULT_ITERATION_MODE)

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

    enable_hitl_gate = bool(opts.get("enable_hitl_gate"))
    gate_stages = opts.get("hitl_gate_stages")
    if not gate_stages:
        gate_stages = list(DEFAULT_HITL_GATE_STAGES)

    gate_stagnant_rounds = opts.get("gate_stagnant_rounds", DEFAULT_GATE_STAGNANT_ROUNDS)
    try:
        gate_stagnant_rounds = max(1, min(int(gate_stagnant_rounds), 4))
    except (TypeError, ValueError):
        gate_stagnant_rounds = DEFAULT_GATE_STAGNANT_ROUNDS

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

    literature_max = opts.get("literature_max_papers", DEFAULT_LITERATURE_MAX_PAPERS)
    try:
        literature_max = max(1, min(int(literature_max), 30))
    except (TypeError, ValueError):
        literature_max = DEFAULT_LITERATURE_MAX_PAPERS

    evidence_max_rounds = opts.get("evidence_reasoning_max_rounds", DEFAULT_EVIDENCE_REASONING_MAX_ROUNDS)
    try:
        evidence_max_rounds = max(1, min(int(evidence_max_rounds), 3))
    except (TypeError, ValueError):
        evidence_max_rounds = DEFAULT_EVIDENCE_REASONING_MAX_ROUNDS

    return {
        "iteration_mode": iteration_mode,
        "pipeline_mode": mode,
        "num_ideas": num_ideas,
        "discovery_max_rounds": max_rounds,
        "force_sandbox": mode == PipelineMode.DISCOVERY.value or bool(opts.get("force_sandbox")),
        "enable_plot_vlm_critique": opts.get("enable_plot_vlm_critique", False),
        "enable_teaching_auto_refinement": bool(opts.get("enable_teaching_auto_refinement")),
        "teaching_auto_refinement_max": DEFAULT_TEACHING_AUTO_REFINEMENT_MAX,
        "enable_experiment_self_correction": bool(opts.get("enable_experiment_self_correction", True)),
        "experiment_self_correction_max": max(
            1,
            min(int(opts.get("experiment_self_correction_max", DEFAULT_EXPERIMENT_SELF_CORRECTION_MAX)), 4),
        ),
        "auto_gap_enrichment_on_data_gap": bool(opts.get("auto_gap_enrichment_on_data_gap", True)),
        "sandbox_use_docker": bool(opts.get("sandbox_use_docker")),
        "enable_hitl_gate": enable_hitl_gate,
        "hitl_gate_stages": list(gate_stages),
        "enable_executability_gate": opts.get("enable_executability_gate", True),
        "gate_stagnant_rounds": gate_stagnant_rounds,
        "min_improvement_delta": 0.0,
        "enable_gap_search": opts.get("enable_gap_search", False),
        "enable_hf_auto_import": opts.get("enable_hf_auto_import", True),
        "coverage_gap_threshold": coverage_threshold,
        "data_spec_gap_threshold": data_spec_threshold,
        "max_gap_rounds": max_gap_rounds,
        "enable_pro_con_adversarial": bool(enable_pro_con),
        "adversarial_mode": adversarial_mode,
        "con_challenge_max_rounds": con_max_rounds,
        "enable_hypothesis_evolution": bool(opts.get("enable_hypothesis_evolution", True)),
        "enable_counterfactual_preview": bool(opts.get("enable_counterfactual_preview", False)),
        "literature_max_papers": literature_max,
        "evidence_reasoning_max_rounds": evidence_max_rounds,
        "enable_science_iteration_observe": opts.get("enable_science_iteration_observe", True),
        # discovery_auto 保持全自动；其余模式默认在可行性评估后暂停
        "pause_after_hypothesis_review": (
            False
            if iteration_mode == IterationMode.DISCOVERY_AUTO.value
            else bool(opts.get("pause_after_hypothesis_review", DEFAULT_PAUSE_AFTER_HYPOTHESIS_REVIEW))
        ),
    }
