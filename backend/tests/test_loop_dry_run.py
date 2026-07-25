"""Loop dry-run：人工主导模式回显。"""
from app.services.loops.dry_run import simulate_loop_decisions


def test_simulate_loop_decisions_human_default():
    result = simulate_loop_decisions(run_options={"pipeline_mode": "teaching"})
    assert result["pipeline_mode"] == "teaching"
    assert result["iteration_mode"] == "human"
    assert result["teaching_config"]["enable_hitl_gate"] is False
    assert result["teaching_config"]["enable_teaching_auto_refinement"] is False


def test_simulate_loop_decisions_legacy_modes_force_human():
    for mode in ("teaching_auto", "discovery_auto"):
        result = simulate_loop_decisions(run_options={"iteration_mode": mode})
        assert result["iteration_mode"] == "human"
        assert result["teaching_config"]["enable_teaching_auto_refinement"] is False
        assert "人工主导" in result["summary"]
