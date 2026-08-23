"""单阶段原地重跑（方案 A）测试。"""
import uuid
from datetime import datetime

import pytest

from app.models.pipeline import (
    PipelineRun,
    PipelineStage,
    PipelineStageExecution,
    PipelineStatus,
)
from app.services.pipeline_service import PipelineService, STAGE_DEFS


@pytest.fixture
def pipeline_run_with_stages(db_session):
    run = PipelineRun(
        id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        project_id="proj-1",
        research_question="测试问题",
        status=PipelineStatus.COMPLETED,
        version=1,
        extra_metadata={},
    )
    db_session.add(run)
    db_session.flush()

    for idx, stage_def in enumerate(STAGE_DEFS):
        db_session.add(
            PipelineStageExecution(
                id=str(uuid.uuid4()),
                pipeline_run_id=run.id,
                stage=stage_def["db_stage_enum"],
                stage_order=idx + 1,
                status=PipelineStatus.COMPLETED,
                output_data={"stage": stage_def["key"], "ok": True},
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
        )
    db_session.commit()
    return run


def test_single_stage_rerun_keeps_same_run_id(db_session, pipeline_run_with_stages):
    run = pipeline_run_with_stages
    svc = PipelineService(db_session)

    returned = svc.start_rerun_from_stage(
        project_id="proj-1",
        parent_run_id=run.run_id,
        from_stage="literature_mining",
        rerun_mode="single_stage",
    )

    assert returned == run.run_id

    db_session.refresh(run)
    assert run.version == 2
    meta = run.extra_metadata or {}
    assert meta.get("in_place_rerun") is True
    assert meta.get("rerun_from_stage") == "literature_mining"
    assert meta.get("downstream_stale_from") == "literature_mining"

    stages = (
        db_session.query(PipelineStageExecution)
        .filter(PipelineStageExecution.pipeline_run_id == run.id)
        .order_by(PipelineStageExecution.stage_order)
        .all()
    )
    lit = next(s for s in stages if s.stage == PipelineStage.LITERATURE_MINING)
    assert lit.status == PipelineStatus.PENDING
    assert lit.output_data is None
    assert (lit.extra_metadata or {}).get("revision_history")

    # 未创建新 run
    count = db_session.query(PipelineRun).filter(PipelineRun.project_id == "proj-1").count()
    assert count == 1


def test_from_stage_onward_creates_new_run(db_session, pipeline_run_with_stages):
    run = pipeline_run_with_stages
    svc = PipelineService(db_session)
    before = db_session.query(PipelineRun).filter(PipelineRun.project_id == "proj-1").count()

    new_run_id = svc.start_rerun_from_stage(
        project_id="proj-1",
        parent_run_id=run.run_id,
        from_stage="literature_mining",
        rerun_mode="from_stage_onward",
    )

    assert new_run_id != run.run_id
    after = db_session.query(PipelineRun).filter(PipelineRun.project_id == "proj-1").count()
    assert after == before + 1


def test_in_place_from_stage_onward_resets_literature_and_downstream(
    db_session, pipeline_run_with_stages
):
    run = pipeline_run_with_stages
    run.status = PipelineStatus.HUMAN_REVIEW_REQUIRED
    run.extra_metadata = {
        "hitl_gate": {
            "paused": True,
            "stage": "literature_mining",
            "cleared_stages": [],
        },
        "pipeline_checkpoint": {
            "resume_phase": "after_literature_mining",
            "results": {"literature_mining": {"facts": []}},
        },
    }
    db_session.commit()

    svc = PipelineService(db_session)
    returned = svc.start_rerun_from_stage(
        project_id="proj-1",
        parent_run_id=run.run_id,
        from_stage="literature_mining",
        rerun_mode="from_stage_onward",
        in_place=True,
        run_options={"pause_after_literature_mining": False},
    )

    assert returned == run.run_id
    db_session.refresh(run)
    meta = run.extra_metadata or {}
    assert meta.get("in_place_rerun") is True
    assert meta.get("rerun_mode") == "from_stage_onward"
    assert meta.get("rerun_from_stage") == "literature_mining"
    assert meta.get("pipeline_checkpoint") is None
    assert "literature_mining" in (meta.get("hitl_gate") or {}).get("cleared_stages", [])
    assert (meta.get("hitl_gate") or {}).get("paused") is False
    assert svc._rerun_single_stage_only is False
    assert svc._start_idx == 1

    stages = (
        db_session.query(PipelineStageExecution)
        .filter(PipelineStageExecution.pipeline_run_id == run.id)
        .order_by(PipelineStageExecution.stage_order)
        .all()
    )
    by_key = {
        (s.stage.value if hasattr(s.stage, "value") else str(s.stage)): s for s in stages
    }
    assert by_key["problem_understanding"].status == PipelineStatus.COMPLETED
    assert by_key["problem_understanding"].output_data is not None
    for key in (
        "literature_mining",
        "knowledge_gap",
        "hypothesis_generation",
        "hypothesis_review",
        "iterative_experiment",
        "report_generation",
    ):
        assert by_key[key].status == PipelineStatus.PENDING
        assert by_key[key].output_data is None
