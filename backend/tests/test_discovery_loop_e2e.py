"""Discovery 迭代控制与停滞判断测试"""
from app.core.iteration_control import evaluate_discovery_continuation


def test_discovery_continuation_stops_on_stagnation():
    trend = [
        {"stage": "discovery_r1", "cqs": 70},
        {"stage": "discovery_r2", "cqs": 71},
        {"stage": "discovery_r3", "cqs": 71.5},
    ]
    result = evaluate_discovery_continuation(
        trend,
        round_num=3,
        min_improvement_delta=3.0,
        stagnant_rounds=2,
    )
    assert result["action"] == "stop_stagnant"
    assert result["reason"]


def test_discovery_continuation_continues_when_improving():
    trend = [
        {"stage": "discovery_r1", "cqs": 60},
        {"stage": "discovery_r2", "cqs": 72},
    ]
    result = evaluate_discovery_continuation(
        trend,
        round_num=2,
        min_improvement_delta=3.0,
    )
    assert result["action"] == "continue"


def test_discovery_continuation_warns_on_small_delta():
    trend = [
        {"stage": "discovery_r1", "cqs": 60},
        {"stage": "discovery_r2", "cqs": 61},
        {"stage": "discovery_r3", "cqs": 61.5},
    ]
    result = evaluate_discovery_continuation(
        trend,
        round_num=3,
        min_improvement_delta=3.0,
        stagnant_rounds=3,
    )
    assert result["action"] in ("continue_with_warning", "stop_stagnant")
