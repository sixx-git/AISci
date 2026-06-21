"""假设树服务单元测试"""
from app.services.hypothesis_tree_service import get_hypothesis_tree_service


def test_build_and_prune_keeps_top_branches():
    svc = get_hypothesis_tree_service()
    hypotheses = [
        {
            "hypothesis": "H1 high evidence",
            "evidence_level": "high",
            "supporting_fact_ids": ["f1", "f2"],
            "validation_target": "accuracy",
            "expected_measurable_effect": "+5%",
        },
        {
            "hypothesis": "H2 medium",
            "evidence_level": "medium",
            "supporting_fact_ids": ["f1"],
        },
        {
            "hypothesis": "H3 low off topic",
            "evidence_level": "low",
            "off_topic": True,
        },
        {
            "hypothesis": "H4 medium backup",
            "evidence_level": "medium",
            "supporting_fact_ids": ["f2"],
        },
    ]
    alignments = [
        {"alignment_score": 90, "off_topic": False},
        {"alignment_score": 75, "off_topic": False},
        {"alignment_score": 30, "off_topic": True},
        {"alignment_score": 70, "off_topic": False},
    ]
    facts = [{"fact_id": "f1"}, {"fact_id": "f2"}]

    tree = svc.build_and_prune(hypotheses, alignments, facts, max_branches=2)

    assert len(tree["branches"]) == 2
    assert tree["selected_branch_id"] == tree["branches"][0]["branch_id"]
    assert tree["branches"][0]["composite_score"] >= tree["branches"][1]["composite_score"]
    assert len(tree["pruned_branches"]) >= 1
    assert tree["iteration_summary"]
    assert tree["quality_trend"]
