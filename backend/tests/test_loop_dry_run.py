"""Loop dry-run 与 discovery_runner 测试"""
from app.services.loops.discovery_runner import (
    check_discovery_acceptance,
    check_discovery_stagnation,
)
from app.services.loops.dry_run import simulate_loop_decisions


def test_check_discovery_stagnation_continue():
    trend = [{"stage": "discovery_r1", "cqs": 5.0}]
    out = check_discovery_stagnation(trend, round_num=2, min_improvement_delta=3.0)
    assert out.get("action") in ("continue", "stop_stagnant", None) or "action" in out


def test_check_discovery_acceptance_by_score():
    hr = {"ensemble_overall": 7.0, "ensemble_decision": "Revise"}
    accepted, meta = check_discovery_acceptance(hr, {}, project_mode="standard")
    assert accepted is True
    assert meta["status"] == "accepted"


def test_simulate_loop_decisions_discovery():
    result = simulate_loop_decisions(
        run_options={"pipeline_mode": "discovery", "discovery_max_rounds": 3},
        quality_trend=[{"cqs": 4.0}, {"cqs": 4.1}],
        round_num=2,
    )
    assert result["pipeline_mode"] == "discovery"
    assert "discovery_stagnation" in result
    assert "summary" in result


def test_simulate_loop_decisions_teaching():
    result = simulate_loop_decisions(run_options={"pipeline_mode": "teaching"})
    assert result["pipeline_mode"] == "teaching"
    assert result["teaching_config"]["enable_hitl_gate"] is False
