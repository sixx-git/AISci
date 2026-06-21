"""验证反馈与假设树 pilot 融合测试"""
from app.services.hypothesis_tree_service import get_hypothesis_tree_service
from app.services.pipeline_service import PipelineService


def test_build_validation_feedback_from_sandbox():
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    constraints = svc._build_validation_feedback_constraints(
        {
            "sandbox_execution": {
                "success": False,
                "return_code": 1,
                "stderr": "ModuleNotFoundError: sklearn",
            },
            "warnings": ["数据量较小"],
        },
        {
            "skill_outputs": {
                "experiment_sanity_check": {
                    "data": {
                        "executable": False,
                        "recommendations": ["补充 baseline"],
                    },
                },
            },
        },
    )
    assert any("沙箱执行失败" in c for c in constraints)
    assert any("sanity" in c.lower() or "可执行" in c for c in constraints)


def test_apply_pilot_feedback_reranks_branches():
    tree_svc = get_hypothesis_tree_service()
    hypotheses = [
        {"hypothesis": "H1", "evidence_level": "high", "supporting_fact_ids": ["f1"]},
        {"hypothesis": "H2", "evidence_level": "medium", "supporting_fact_ids": ["f1"]},
    ]
    tree = tree_svc.build_and_prune(hypotheses, [], [{"fact_id": "f1"}], max_branches=2)
    selected_id = tree["selected_branch_id"]

    updated = tree_svc.apply_pilot_feedback(
        tree,
        {
            "sandbox_execution": {
                "success": True,
                "metrics": {"accuracy": 0.91},
            },
        },
        hypotheses,
    )
    assert updated["pilot_feedback_applied"] is True
    selected = next(b for b in updated["branches"] if b["branch_id"] == selected_id)
    assert selected.get("pilot_score") == 8.5
