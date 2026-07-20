"""迭代模式互斥与默认配置测试"""
from app.core.pipeline_modes import (
    DEFAULT_ITERATION_MODE,
    IterationMode,
    PipelineMode,
    resolve_run_options,
)


def test_default_iteration_mode_is_human():
    opts = resolve_run_options({})
    assert opts["iteration_mode"] == DEFAULT_ITERATION_MODE == "human"
    assert opts["enable_hitl_gate"] is False
    assert opts["enable_teaching_auto_refinement"] is False
    assert opts["pipeline_mode"] == PipelineMode.TEACHING.value
    assert opts["pause_after_hypothesis_review"] is True


def test_teaching_auto_mode():
    opts = resolve_run_options({"iteration_mode": "teaching_auto"})
    assert opts["iteration_mode"] == IterationMode.TEACHING_AUTO.value
    assert opts["enable_hitl_gate"] is False
    assert opts["enable_teaching_auto_refinement"] is True
    assert opts["pipeline_mode"] == PipelineMode.TEACHING.value
    assert opts["pause_after_hypothesis_review"] is True


def test_discovery_auto_mode():
    opts = resolve_run_options({"iteration_mode": "discovery_auto", "discovery_max_rounds": 4})
    assert opts["iteration_mode"] == IterationMode.DISCOVERY_AUTO.value
    assert opts["pipeline_mode"] == PipelineMode.DISCOVERY.value
    assert opts["force_sandbox"] is True
    assert opts["discovery_max_rounds"] == 4
    assert opts["enable_teaching_auto_refinement"] is False
    assert opts["pause_after_hypothesis_review"] is False


def test_human_mode_can_disable_feasibility_pause():
    opts = resolve_run_options({"iteration_mode": "human", "pause_after_hypothesis_review": False})
    assert opts["iteration_mode"] == "human"
    assert opts["pause_after_hypothesis_review"] is False


def test_human_mode_can_disable_hitl():
    opts = resolve_run_options({"iteration_mode": "human", "enable_hitl_gate": False})
    assert opts["iteration_mode"] == "human"
    assert opts["enable_hitl_gate"] is False


def test_legacy_pipeline_mode_discovery_maps_to_discovery_auto():
    opts = resolve_run_options({"pipeline_mode": "discovery"})
    assert opts["iteration_mode"] == "discovery_auto"
    assert opts["pipeline_mode"] == "discovery"


def test_pro_con_adversarial_defaults_off():
    opts = resolve_run_options({})
    assert opts["enable_pro_con_adversarial"] is False
    assert opts["adversarial_mode"] == "off"


def test_pro_con_adversarial_string_false_stays_off():
    opts = resolve_run_options({"enable_pro_con_adversarial": "false", "adversarial_mode": "single_group"})
    assert opts["enable_pro_con_adversarial"] is False
    assert opts["adversarial_mode"] == "off"


def test_pro_con_adversarial_can_enable():
    opts = resolve_run_options({"enable_pro_con_adversarial": True})
    assert opts["enable_pro_con_adversarial"] is True
    assert opts["adversarial_mode"] == "single_group"


def test_evidence_reasoning_default_one_round():
    opts = resolve_run_options({})
    assert opts["evidence_reasoning_max_rounds"] == 1


def test_science_iteration_observe_default_on():
    opts = resolve_run_options({})
    assert opts["enable_science_iteration_observe"] is True
