"""文献挖掘后 PDF 交接暂停。"""
from app.core.pipeline_modes import resolve_run_options
from app.services.pipeline_service import PipelineService


def test_pause_after_literature_mining_default_on():
    opts = resolve_run_options({})
    assert opts["pause_after_literature_mining"] is True


def test_pause_after_literature_mining_can_disable():
    opts = resolve_run_options({"pause_after_literature_mining": False})
    assert opts["pause_after_literature_mining"] is False


def test_literature_has_retrievable_papers():
    assert PipelineService._literature_has_retrievable_papers(
        {"literature_mining": {"retrieved_papers": [{"title": "A"}]}}
    )
    assert PipelineService._literature_has_retrievable_papers(
        {"literature_mining": {"literature_selected_count": 3}}
    )
    assert not PipelineService._literature_has_retrievable_papers(
        {"literature_mining": {"facts": [], "retrieved_papers": []}}
    )


def test_literature_hitl_continue_requests_in_place_rerun(db_session):
    """文献门控 continue 应要求原地从 literature_mining 起重跑至结束。"""
    import uuid
    from datetime import datetime

    from app.models.pipeline import PipelineRun, PipelineStatus
    from app.services.stage_human_loop_service import StageHumanLoopService

    run = PipelineRun(
        id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        project_id="proj-lit-hitl",
        research_question="测试",
        status=PipelineStatus.HUMAN_REVIEW_REQUIRED,
        current_stage="literature_mining",
        extra_metadata={
            "hitl_gate": {
                "paused": True,
                "stage": "literature_mining",
                "resume_phase": "after_literature_mining",
                "cleared_stages": [],
                "handoff": "literature_library",
            },
            "pipeline_checkpoint": {
                "resume_phase": "after_literature_mining",
                "results": {"literature_mining": {"facts": [{"id": 1}]}},
            },
        },
        created_at=datetime.utcnow(),
    )
    db_session.add(run)
    db_session.commit()

    svc = StageHumanLoopService(db_session)
    result = svc.resume_hitl_gate(run.run_id, action="continue", inject_feedback=False)

    assert result["action"] == "continue"
    assert result["prepare_in_place_from_stage_onward"] is True
    assert result["rerun_from_stage"] == "literature_mining"
    assert result["resume_phase"] == "after_problem_understanding"

    db_session.refresh(run)
    gate = (run.extra_metadata or {}).get("hitl_gate") or {}
    assert gate.get("paused") is False
    assert "literature_mining" in (gate.get("cleared_stages") or [])
    assert (run.extra_metadata or {}).get("pipeline_checkpoint") is None
