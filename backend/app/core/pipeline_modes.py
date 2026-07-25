"""Pipeline 运行模式 — 仅保留人工主导（human）；历史 teaching_auto / discovery_auto 一律映射为 human。"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class PipelineMode(str, Enum):
    TEACHING = "teaching"
    DISCOVERY = "discovery"  # 仅兼容历史 metadata 读取，运行时不再启用


class IterationMode(str, Enum):
    HUMAN = "human"
    # 已退役：仍保留枚举值以便解析旧 run / 本地配置，resolve 时强制映射为 human
    TEACHING_AUTO = "teaching_auto"
    DISCOVERY_AUTO = "discovery_auto"


VALID_PIPELINE_MODES = {PipelineMode.TEACHING.value, PipelineMode.DISCOVERY.value}
VALID_ITERATION_MODES = {IterationMode.HUMAN.value}

DEFAULT_NUM_IDEAS = 3
DEFAULT_DISCOVERY_MAX_ROUNDS = 3  # 兼容旧字段，运行时不再驱动闭环
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
    IterationMode.HUMAN.value: "人工主导 — 可行性评估后暂停，在迭代实验页完成验证与报告",
}

PIPELINE_MODE_LABELS_ZH = {
    PipelineMode.TEACHING.value: "标准流水线（人工主导）",
    PipelineMode.DISCOVERY.value: "（已退役）Discovery 自动循环",
}


def normalize_pipeline_mode(mode: str | None) -> str:
    """运行时一律使用 teaching；discovery 仅作历史标签时仍可识别。"""
    if mode and mode in VALID_PIPELINE_MODES:
        # 不再进入 discovery 执行路径
        if mode == PipelineMode.DISCOVERY.value:
            return PipelineMode.TEACHING.value
        return mode
    return PipelineMode.TEACHING.value


def resolve_iteration_mode(opts: Dict[str, Any]) -> str:
    """始终返回 human；兼容旧版 iteration_mode / pipeline_mode / enable_* 字段。"""
    return DEFAULT_ITERATION_MODE


def apply_iteration_mode(opts: Dict[str, Any]) -> Dict[str, Any]:
    """强制人工主导：关闭自动精化与 Discovery 循环。"""
    out = dict(opts)
    out["iteration_mode"] = IterationMode.HUMAN.value
    out["pipeline_mode"] = PipelineMode.TEACHING.value
    out["enable_hitl_gate"] = bool(opts.get("enable_hitl_gate", False))
    out["enable_teaching_auto_refinement"] = False
    return out


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """严格解析布尔：避免字符串 \"false\" 被 bool() 当成 True。"""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off", ""):
            return False
        return default
    return bool(value)


def _resolve_post_evolution_enabled(opts: Dict[str, Any]) -> bool:
    if "enable_hypothesis_post_evolution" in opts:
        return bool(opts.get("enable_hypothesis_post_evolution"))
    try:
        from app.core.config import get_settings

        return bool(getattr(get_settings(), "HYPOTHESIS_EVOLUTION_ENABLED", True))
    except Exception:
        return True


def resolve_run_options(options: Dict[str, Any] | None) -> Dict[str, Any]:
    opts = apply_iteration_mode(dict(options or {}))
    mode = normalize_pipeline_mode(opts.get("pipeline_mode"))
    iteration_mode = IterationMode.HUMAN.value

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

    enable_pro_con = _coerce_bool(opts.get("enable_pro_con_adversarial"), False)
    adversarial_mode = opts.get("adversarial_mode", "off")
    if adversarial_mode not in VALID_ADVERSARIAL_MODES:
        adversarial_mode = "off" if not enable_pro_con else "single_group"
    if not enable_pro_con:
        adversarial_mode = "off"
    elif adversarial_mode == "off":
        adversarial_mode = "single_group"
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
        "force_sandbox": bool(opts.get("force_sandbox")),
        "enable_plot_vlm_critique": opts.get("enable_plot_vlm_critique", False),
        "enable_teaching_auto_refinement": False,
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
        "enable_pro_con_adversarial": enable_pro_con,
        "adversarial_mode": adversarial_mode,
        "con_challenge_max_rounds": con_max_rounds,
        "enable_hypothesis_evolution": bool(opts.get("enable_hypothesis_evolution", True)),
        "enable_hypothesis_post_evolution": _resolve_post_evolution_enabled(opts),
        "enable_experiment_memory_save": bool(opts.get("enable_experiment_memory_save", True)),
        "enable_experiment_memory_retrieve": bool(opts.get("enable_experiment_memory_retrieve", True)),
        "enable_counterfactual_preview": bool(opts.get("enable_counterfactual_preview", False)),
        "literature_max_papers": literature_max,
        "evidence_reasoning_max_rounds": evidence_max_rounds,
        "enable_science_iteration_observe": opts.get("enable_science_iteration_observe", True),
        "pause_after_hypothesis_review": bool(
            opts.get("pause_after_hypothesis_review", DEFAULT_PAUSE_AFTER_HYPOTHESIS_REVIEW)
        ),
    }
