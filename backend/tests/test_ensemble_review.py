"""集成评审服务单元测试"""
from app.services.ensemble_review_service import EnsembleReviewService


def test_evidence_rule_score_boosted_by_facts():
    score = EnsembleReviewService._evidence_rule_score({
        "evidence_level": "high",
        "supporting_fact_ids": ["a", "b", "c"],
        "dataset_field_refs": ["col_x"],
    })
    assert score >= 9.0


def test_disagreement_flags_on_high_variance():
    members = [
        {"overall_score": 8.5},
        {"overall_score": 4.0},
        {"overall_score": 7.0},
        {"overall_score": 5.5},
    ]
    flags = EnsembleReviewService._disagreement_flags(members)
    assert "high_variance_between_reviewers" in flags


def test_run_ensemble_sync_reject_low_score(monkeypatch):
    svc = EnsembleReviewService()

    async def fake_mentor(*args, **kwargs):
        return {"readiness_score": 40, "weaknesses": ["证据不足"], "revision_suggestions": ["补充实验"]}

    monkeypatch.setattr(svc, "_run_mentor", fake_mentor)

    result = svc.run_ensemble_sync(
        reviews=[{"hypothesis": "H1", "overall_score": 4.0, "scores": {}, "weaknesses": ["方法模糊"]}],
        hypotheses=[{"evidence_level": "low"}],
        research_question="RQ",
    )

    assert result["decision"] == "Reject"
    assert result["overall"] < 6.5
    assert len(result["ensemble_reviews"]) == 4
