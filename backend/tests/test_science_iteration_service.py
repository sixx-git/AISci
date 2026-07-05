"""科学自迭代服务测试"""
from unittest.mock import MagicMock, patch

from app.schemas.science_iteration import ScienceIterationConfig
from app.services.science_iteration_service import (
    build_hypothesis_provenance,
    build_iteration_round,
    build_material_supplement_plan,
    build_reasoning_chain,
    build_session_from_results,
    resolve_science_iteration_config,
    ScienceIterationOrchestrator,
)


def test_resolve_science_iteration_config_merges_project_and_run():
    cfg = resolve_science_iteration_config(
        {"science_iteration": {"max_rounds": 3, "enabled": True}},
        {"science_iteration_enabled": False, "science_iteration_max_rounds": 4},
    )
    assert cfg.enabled is False
    assert cfg.max_rounds == 4


def test_build_reasoning_chain():
    pu = {"main_contradiction": "矛盾A", "expected_output": ["目标1"]}
    kg = {"knowledge_gaps": [{"description": "缺口1"}]}
    chain = build_reasoning_chain(pu, kg)
    assert any("主要矛盾" in c for c in chain)
    assert any("知识缺口" in c for c in chain)


def test_build_material_supplement_plan_evidence_weak():
    results = {
        "problem_understanding": {"problem_statement": "研究问题X"},
        "knowledge_gap": {"knowledge_gaps": [{"description": "机制不明"}]},
        "hypothesis_generation": {
            "hypotheses": [{"hypothesis": "H1", "supporting_fact_ids": [], "evidence_level": "low"}],
        },
        "hypothesis_review": {
            "skill_outputs": {"ensemble_review": {"decision": "revise", "weaknesses": ["证据不足"]}},
        },
        "data_acquisition": {"coverage_report": {"completeness_score": 55}},
    }
    plan = build_material_supplement_plan(results, trigger="auto")
    assert "evidence_weak" in plan.triggers
    assert "data_coverage_low" in plan.triggers
    assert "review_reject" in plan.triggers
    assert plan.actions
    assert plan.suggested_queries


def test_build_iteration_round_delta():
    results = {
        "hypothesis_generation": {
            "hypotheses": [{"hypothesis": "假设文本"}],
            "hypothesis_tree": {"branches": [{"composite_score": 7.2}]},
        },
        "hypothesis_review": {
            "skill_outputs": {"ensemble_review": {"overall": 8.0, "decision": "accept"}},
        },
    }
    from app.schemas.science_iteration import IterationRoundScores

    prev = IterationRoundScores(ensemble_overall=6.5, hypothesis_tree=6.0)
    rec = build_iteration_round(2, "review_refine_complete", results, label="R2", prev_scores=prev)
    assert rec.round == 2
    assert "ensemble_delta" in rec.delta_from_prev
    assert rec.delta_from_prev["ensemble_delta"] == 1.5


def test_build_session_from_results():
    meta = {
        "science_iteration_session_id": "sess-1",
        "science_iteration_rounds": [
            {
                "round": 1,
                "trigger": "initial",
                "label": "R1_initial",
                "hypothesis_preview": "H",
                "actions_taken": [],
                "scores": {},
                "delta_from_prev": {},
                "snapshot_label": "R1_initial",
            },
        ],
        "version_snapshots": [{"round": 1, "label": "R1", "hypothesis": "H"}],
    }
    results = {
        "hypothesis_review": {
            "skill_outputs": {"ensemble_review": {"decision": "accept", "overall": 8.5}},
        },
    }
    session = build_session_from_results("proj-1", "run-1", results, extra_metadata=meta)
    assert session.session_id == "sess-1"
    assert len(session.rounds) == 1
    assert session.current_best.get("ensemble_decision") == "accept"
    assert len(session.version_snapshots) == 1


def test_orchestrator_record_milestone_when_disabled():
    pipeline = MagicMock()
    pipeline.db_pipeline_run = MagicMock(extra_metadata={})
    pipeline._run_options = {}
    pipeline._persist_extra_metadata = MagicMock()

    db = MagicMock()
    project = MagicMock()
    project.config = {"science_iteration": {"enabled": False}}
    with patch("app.services.project_service.ProjectService") as ps:
        ps.return_value.get_project.return_value = project
        orch = ScienceIterationOrchestrator(db, pipeline)
        orch.record_milestone({"hypothesis_generation": {}}, "initial")
        pipeline._persist_extra_metadata.assert_not_called()


def test_orchestrator_ensemble_accepted():
    pipeline = MagicMock()
    pipeline.db_pipeline_run = MagicMock(extra_metadata={})
    pipeline._run_options = {}
    orch = ScienceIterationOrchestrator(MagicMock(), pipeline)
    cfg = ScienceIterationConfig(min_ensemble_score=7.5)
    ok, score = orch._ensemble_accepted(
        {"hypothesis_review": {"skill_outputs": {"ensemble_review": {"decision": "accept", "overall": 8.0}}}},
        cfg,
    )
    assert ok is True
    assert score == 8.0


def test_build_hypothesis_provenance_raises_when_missing():
    db = MagicMock()
    with patch("app.services.hypothesis_service.HypothesisService") as hs:
        hs.return_value.get_hypothesis_by_id.return_value = None
        try:
            build_hypothesis_provenance(db, "missing-id")
            assert False, "expected ValueError"
        except ValueError as e:
            assert "不存在" in str(e)
