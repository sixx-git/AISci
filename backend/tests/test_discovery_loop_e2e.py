"""Discovery 迭代控制与停滞判断测试"""
from app.core.iteration_control import evaluate_discovery_continuation


def test_discovery_continuation_stops_on_stagnation():
    trend = [
        {"stage": "discovery_r1", "passed": False},
        {"stage": "discovery_r2", "passed": False},
        {"stage": "discovery_r3", "passed": False},
    ]
    result = evaluate_discovery_continuation(
        trend,
        round_num=3,
        stagnant_rounds=2,
    )
    assert result["action"] == "stop_stagnant"
    assert result["reason"]


def test_discovery_continuation_continues_when_improved():
    trend = [
        {"stage": "discovery_r1", "passed": False},
        {"stage": "discovery_r2", "passed": True},
    ]
    result = evaluate_discovery_continuation(
        trend,
        round_num=2,
    )
    assert result["action"] == "continue"


def test_discovery_continuation_warns_on_repeated_fail():
    trend = [
        {"stage": "discovery_r1", "passed": False},
        {"stage": "discovery_r2", "passed": False},
        {"stage": "discovery_r3", "passed": False},
    ]
    result = evaluate_discovery_continuation(
        trend,
        round_num=3,
        stagnant_rounds=3,
    )
    assert result["action"] in ("continue_with_warning", "stop_stagnant")
