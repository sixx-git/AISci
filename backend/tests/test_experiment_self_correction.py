"""实验设计↔验证 自迭代自纠错环回归测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.core.iterative_science import (
    build_general_replan_actions,
    evaluate_general_validation_improvement,
    needs_experiment_self_correction,
)


def test_build_general_replan_actions_sandbox_failure():
    actions = build_general_replan_actions(
        {"experiment_spec": {"primary_metric": "accuracy"}},
        {
            "sandbox_execution": {
                "success": False,
                "stderr": "ValueError: no numeric columns",
            },
            "verifiable_passed": False,
        },
        {"datasets": [{"filename": "a.csv", "columns": ["x", "y"]}]},
    )
    ids = {a["action_id"] for a in actions}
    assert "fix_analysis_script" in ids


def test_needs_correction_when_sandbox_incomplete():
    results = {
        "experiment_design": {
            "project_datasets": [{"filename": "a.csv"}],
            "data_requirements": {"uploaded_dataset_count": 1},
        },
        "small_validation": {
            "sandbox_execution": {
                "success": True,
                "output_complete": False,
                "sandbox_incomplete": True,
            },
            "verifiable_passed": False,
        },
    }
    needs, reasons, _ = needs_experiment_self_correction(results, correction_count=0, max_rounds=2)
    assert needs is True
    assert any("不完整" in r or "replan" in r for r in reasons)


def test_needs_correction_stops_when_no_uploaded_data():
    results = {
        "experiment_design": {
            "data_gap": ["无数据"],
            "data_requirements": {"upload_status": "pending_upload", "uploaded_dataset_count": 0},
        },
        "small_validation": {},
    }
    needs, reasons, actions = needs_experiment_self_correction(results, correction_count=0, max_rounds=2)
    assert needs is False
    assert any("上传" in r for r in reasons)
    assert any(a["action_id"] == "upload_required_data" for a in actions)


def test_evaluate_general_validation_improvement():
    before = {
        "sandbox_execution": {"success": False, "output_complete": False},
        "verifiable_passed": False,
    }
    after = {
        "sandbox_execution": {
            "success": True,
            "output_complete": True,
            "metrics": {"primary_metric": 0.9},
            "plots": [{"plot_id": "p1"}],
        },
        "verifiable_passed": True,
    }
    imp = evaluate_general_validation_improvement(before, after)
    assert imp["improved"] is True
    assert imp["score_after"] > imp["score_before"]


def test_self_correction_loop_runs_one_round():
    from app.services.pipeline_service import PipelineService

    svc = PipelineService(MagicMock())
    svc.run_id = "run-test"
    svc.db_pipeline_run = MagicMock(project_id="p1", extra_metadata={})
    svc._run_options = {
        "enable_experiment_self_correction": True,
        "experiment_self_correction_max": 2,
        "iteration_mode": "human",
        "enable_executability_gate": True,
        "enable_gap_search": False,
    }
    svc._record_closed_loop_event = MagicMock()
    svc._record_closed_loop_decision = MagicMock()
    svc._capture_iteration_snapshot = MagicMock(return_value={})
    svc._persist_audit_record = MagicMock()
    svc._build_validation_feedback_constraints = MagicMock(return_value=["fix script"])
    svc._build_pilot_results_payload = MagicMock(return_value={})
    svc._get_science_iteration_orchestrator = MagicMock(
        return_value=MagicMock(record_milestone=MagicMock())
    )

    results = {
        "hypothesis_review": {"reviews": [{"hypothesis": "H1"}]},
        "experiment_design": {
            "methods": "m",
            "project_datasets": [{"filename": "a.csv", "file_path": "/tmp/a.csv"}],
            "data_requirements": {"uploaded_dataset_count": 1},
        },
        "small_validation": {
            "sandbox_execution": {"success": False, "stderr": "fail"},
            "verifiable_passed": False,
        },
    }

    ed_calls = {"n": 0}
    sv_calls = {"n": 0}

    def fake_ed(*a, **k):
        ed_calls["n"] += 1
        return {**results["experiment_design"], "methods": f"m{ed_calls['n']}"}

    def fake_sv(*a, **k):
        sv_calls["n"] += 1
        return {
            "sandbox_execution": {
                "success": True,
                "output_complete": True,
                "metrics": {"primary_metric": 0.8},
                "plots": [{"plot_id": "p1"}],
            },
            "verifiable_passed": True,
        }

    svc._run_stage = MagicMock(side_effect=lambda stages, idx, res, rq, pid, fn: res.update(
        {"experiment_design": fake_ed()} if idx == 5 else {"small_validation": fake_sv()}
    ))
    svc._exec_experiment_design = fake_ed
    svc._exec_small_validation = fake_sv
    svc._apply_executability_gate = MagicMock(return_value={"passed": True})
    svc._apply_post_validation_updates = MagicMock(
        side_effect=lambda res, sv: res.update({"small_validation": sv})
    )

    meta = svc._run_experiment_self_correction_loop(
        [], results, "rq", "p1", "general", validation_skipped=False
    )
    assert meta is not None
    assert meta.get("total_rounds") == 1
    assert ed_calls["n"] == 1
    assert sv_calls["n"] == 1
