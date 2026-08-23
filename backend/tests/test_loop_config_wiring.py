"""运行配置面板：候选假设数 / 文献检索篇数 / Gap 补搜 / 证据链迭代决策 接线测试。"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.pipeline_modes import resolve_run_options
from app.services.pipeline_service import PipelineService


def test_loop_config_maps_num_ideas_and_literature_max_papers():
    opts = resolve_run_options(
        {
            "num_ideas": 5,
            "literature_max_papers": 20,
            "enable_gap_search": True,
            "evidence_reasoning_max_rounds": 3,
        }
    )
    assert opts["num_ideas"] == 5
    assert opts["literature_max_papers"] == 20
    assert opts["enable_gap_search"] is True
    assert opts["evidence_reasoning_max_rounds"] == 3


def test_pipeline_service_literature_top_k_from_run_options():
    svc = PipelineService(db=MagicMock())
    svc._run_options = {"literature_max_papers": 18}
    assert svc._get_literature_top_k() == 18


def test_gap_literature_enrichment_skipped_when_disabled():
    svc = PipelineService(db=MagicMock())
    svc._run_options = {"enable_gap_search": False}
    out = svc._try_gap_literature_enrichment("proj-1", "rq", {"knowledge_gap": {"knowledge_gaps": [{"description": "g1"}]}})
    assert out is None


def test_gap_literature_enrichment_calls_discovery_refresh():
    svc = PipelineService(db=MagicMock())
    svc._run_options = {"enable_gap_search": True, "literature_max_papers": 12}
    svc.db_pipeline_run = MagicMock()
    svc._record_closed_loop_event = MagicMock()
    svc._enrich_literature_mining = lambda x: x
    svc._safe_model_dump = lambda x: x if isinstance(x, dict) else {"facts": [{"fact_id": "f1"}]}

    previous = {"facts": []}
    refreshed = {"facts": [{"fact_id": "f1"}, {"fact_id": "f2"}]}

    with patch("app.services.pipeline_service.get_literature_mining_agent") as mock_agent_factory:
        agent = MagicMock()
        agent.mine_discovery_refresh.return_value = refreshed
        mock_agent_factory.return_value = agent

        out = svc._try_gap_literature_enrichment(
            "proj-1",
            "研究问题",
            {
                "knowledge_gap": {"knowledge_gaps": [{"description": "缺少纵向证据"}]},
                "literature_mining": previous,
                "problem_understanding": {"keywords": ["a"], "research_domain": "bio"},
            },
        )

    assert out == refreshed
    agent.mine_discovery_refresh.assert_called_once()
    kwargs = agent.mine_discovery_refresh.call_args.kwargs
    assert kwargs["top_k"] == 12
    assert kwargs["refinement_queries"] == ["缺少纵向证据"]


def test_evidence_iteration_decision_approve_starts_fork_rerun(db_session, test_project):
    from app.models.pipeline import PipelineRun, PipelineStatus

    run = PipelineRun(
        id="run-row-1",
        run_id="run-evidence-1",
        project_id=test_project.id,
        research_question="test rq",
        status=PipelineStatus.COMPLETED,
        input_data={"options": {"num_ideas": 4, "literature_max_papers": 15}},
        output_data={
            "coordinator_hints": [
                {
                    "id": "hint-1",
                    "pattern_id": "hg_all_low_evidence",
                    "decision_status": "awaiting_user",
                    "stage": "hypothesis_generation",
                    "message": "low evidence",
                    "remediation": "hint_evidence_iteration",
                    "action": {"type": "hint", "suggestion": "evidence_iteration_decision", "description": ""},
                }
            ]
        },
    )
    db_session.add(run)
    db_session.commit()

    svc = PipelineService(db=db_session)
    with patch.object(svc, "_persist_hints_for_run"), patch.object(
        svc, "start_rerun_from_stage", return_value="run-evidence-2"
    ) as mock_rerun:
        result = svc.respond_evidence_iteration_decision(
            project_id=test_project.id,
            run_id="run-evidence-1",
            hint_id="hint-1",
            decision="approve",
        )

    assert result["decision"] == "approve"
    assert result["run_id"] == "run-evidence-2"
    mock_rerun.assert_called_once()
    call_kwargs = mock_rerun.call_args.kwargs
    assert call_kwargs["from_stage"] == "literature_mining"
    assert call_kwargs["rerun_mode"] == "from_stage_onward"
