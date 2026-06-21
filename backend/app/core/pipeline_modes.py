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
PLOT_CRITIQUE_PASS_SCORE = 6.5
ENSEMBLE_ACCEPT_SCORE = 6.5


def normalize_pipeline_mode(mode: str | None) -> str:
    if mode and mode in VALID_PIPELINE_MODES:
        return mode
    return PipelineMode.TEACHING.value


PIPELINE_MODE_LABELS_ZH = {
    PipelineMode.TEACHING.value: "Teaching 模式 — 强 HITL，适合研究生仿真",
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
    }
