"""用户手动暂停 / 续跑。"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.pipeline_exceptions import UserPause
from app.models.pipeline import PipelineStatus
from app.services.pipeline_service import PipelineService, STAGE_DEFS


CHINA_TZ = timezone(timedelta(hours=8))


def _mock_run(status=PipelineStatus.RUNNING, meta=None):
    run = MagicMock()
    run.run_id = "run-pause-1"
    run.status = status
    run.extra_metadata = meta or {}
    run.current_stage = None
    run.error_message = None
    return run


def test_request_user_pause_sets_flag():
    run = _mock_run()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = run

    out = PipelineService.request_user_pause(db, "run-pause-1")
    assert out["accepted"] is True
    assert out["already_requested"] is False
    assert run.extra_metadata["user_pause"]["requested"] is True
    db.commit.assert_called()


def test_request_user_pause_rejects_non_running():
    run = _mock_run(status=PipelineStatus.COMPLETED)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = run

    with pytest.raises(ValueError, match="仅运行中"):
        PipelineService.request_user_pause(db, "run-pause-1")


def test_apply_user_pause_raises_and_sets_paused():
    svc = PipelineService.__new__(PipelineService)
    svc.db = MagicMock()
    svc.run_id = "run-pause-1"
    svc.db_pipeline_run = _mock_run(
        meta={"user_pause": {"requested": True}},
    )
    svc._checkpoint_safe_results = lambda results: {"ok": True}
    svc._record_closed_loop_event = MagicMock()

    with pytest.raises(UserPause) as ei:
        svc._apply_user_pause("literature_mining", {"literature_mining": {"facts": []}})

    assert ei.value.stage_key == "literature_mining"
    assert svc.db_pipeline_run.status == PipelineStatus.PAUSED
    up = svc.db_pipeline_run.extra_metadata["user_pause"]
    assert up["paused"] is True
    assert up["requested"] is False
    assert up["resume_phase"] == "after_literature_mining"
    assert svc.db_pipeline_run.extra_metadata["pipeline_checkpoint"]["resume_phase"] == (
        "after_literature_mining"
    )


def test_resume_user_pause_restores_running():
    run = _mock_run(
        status=PipelineStatus.PAUSED,
        meta={
            "user_pause": {
                "paused": True,
                "stage": "knowledge_gap",
                "resume_phase": "after_knowledge_gap",
            },
            "pipeline_checkpoint": {
                "results": {},
                "resume_phase": "after_knowledge_gap",
                "kind": "user_pause",
            },
        },
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = run

    out = PipelineService.resume_user_pause(db, "run-pause-1")
    assert out["status"] == "running"
    assert out["resume_phase"] == "after_knowledge_gap"
    assert run.status == PipelineStatus.RUNNING
    assert run.extra_metadata["user_pause"]["paused"] is False


def test_resume_phase_mapping_covers_early_stages():
    svc = PipelineService.__new__(PipelineService)
    assert svc._resume_phase_to_start_idx("after_problem_understanding") == 1
    assert svc._resume_phase_to_start_idx("after_literature_mining") == 2
    assert svc._resume_phase_to_start_idx("after_knowledge_gap") == 3
    assert len(STAGE_DEFS) >= 7
