"""闭环质量验收单元测试"""
from app.services.closed_loop_quality_service import compute_quality_acceptance


def test_quality_acceptance_pass_when_accepted():
    result = compute_quality_acceptance(
        quality_trend=[
            {"stage": "ideation", "score": 6.0},
            {"stage": "discovery_r2", "score": 7.5},
        ],
        closed_loop_events=[
            {"type": "sandbox_validation", "success": True},
        ],
        hypothesis_review={
            "skill_outputs": {
                "ensemble_review": {"decision": "Accept", "overall": 7.2},
            },
        },
    )
    assert result["accepted"] is True
    assert result["score_improved"] is True
    assert result["verdict"] == "pass"


def test_quality_acceptance_stagnant_when_not_improved():
    result = compute_quality_acceptance(
        quality_trend=[
            {"stage": "a", "score": 7.0},
            {"stage": "b", "score": 6.5},
        ],
        hypothesis_review={
            "skill_outputs": {"ensemble_review": {"decision": "Revise", "overall": 5.5}},
        },
    )
    assert result["accepted"] is False
    assert result["score_improved"] is False
    assert result["verdict"] in ("needs_review", "stagnant")
