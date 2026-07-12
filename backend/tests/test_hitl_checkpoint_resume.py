"""HITL checkpoint 恢复与假设回填测试。"""
from types import SimpleNamespace

from app.services.data_finder_slim import (
    slim_hypothesis_generation_for_checkpoint,
    slim_results_for_checkpoint,
)
from app.services.pipeline_service import PipelineService


def test_resume_phase_to_start_idx_hypothesis_generation():
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    assert svc._resume_phase_to_start_idx("after_hypothesis_generation") == 4


def test_resume_phase_to_start_idx_hypothesis_review():
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    assert svc._resume_phase_to_start_idx("after_hypothesis_review") == 5


def test_resume_phase_unknown_defaults_zero():
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    assert svc._resume_phase_to_start_idx("after_unknown") == 0


def test_slim_hypothesis_generation_preserves_hypotheses_list():
    huge_rationale = "x" * 50_000
    output = {
        "summary": "ok",
        "hypotheses": [
            {
                "hypothesis": "H1",
                "rationale": huge_rationale,
                "novelty": "n",
                "testability": "t",
                "required_data": "d",
                "possible_method": "m",
                "risk": "r",
                "supporting_fact_ids": ["f1"],
            }
        ],
        "alignment": {"alignments": [{"alignment_score": 90}], "summary": "align"},
    }
    slimmed = slim_hypothesis_generation_for_checkpoint(output)
    assert len(slimmed["hypotheses"]) == 1
    assert slimmed["hypotheses"][0]["hypothesis"] == "H1"
    assert len(slimmed["hypotheses"][0]["rationale"]) <= 2003

    checkpoint = slim_results_for_checkpoint({"hypothesis_generation": output})
    assert "_truncated" not in checkpoint.get("hypothesis_generation", {})
    assert len(checkpoint["hypothesis_generation"]["hypotheses"]) == 1


def test_repair_checkpoint_results_backfills_truncated_hypothesis_generation():
    full_hg = {
        "hypotheses": [{"hypothesis": "H1", "rationale": "r"}],
        "summary": "s",
    }
    exec_row = SimpleNamespace(output_data=full_hg)
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    svc.run_id = "test-run"
    svc.db_pipeline_run = SimpleNamespace(project_id="proj-1")
    svc.db_stage_executions = {4: exec_row}

    results = {
        "hypothesis_generation": {"_truncated": True, "preview": "..."},
        "hypothesis_review": {"reviews": [], "summary": "empty"},
    }
    new_idx = svc._repair_checkpoint_results(results, start_idx=6)

    assert new_idx == 4
    assert len(results["hypothesis_generation"]["hypotheses"]) == 1
    assert "hypothesis_review" not in results
    assert "experiment_design" not in results


def test_hydrate_hypothesis_generation_from_db_stage():
    full_hg = {
        "hypotheses": [
            {
                "hypothesis": "H2",
                "rationale": "r2",
                "novelty": "n",
                "testability": "t",
                "required_data": "d",
                "possible_method": "m",
                "risk": "r",
            }
        ],
        "summary": "from db",
    }
    exec_row = SimpleNamespace(output_data=full_hg)
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    svc.db_stage_executions = {4: exec_row}

    hg = svc._hydrate_hypothesis_generation({"_truncated": True}, project_id="")
    assert len(hg["hypotheses"]) == 1
    assert hg["hypotheses"][0]["hypothesis"] == "H2"
