"""experiment_spec 对齐小样验证脚本回归测试。"""
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.small_validation_agent import SmallValidationAgent
from app.services.analysis_script_generator import build_spec_validation_script
from app.services.experiment_sandbox_service import ExperimentSandboxService
from app.services.experiment_spec_service import (
    assess_sandbox_spec_alignment,
    assess_validation_readiness,
    is_proxy_validation_metrics,
)
from app.skills.experiment.result_verification_skill import ResultVerificationSkill


@pytest.fixture
def sandbox_svc():
    return ExperimentSandboxService()


def test_build_spec_validation_script_produces_aligned_metrics(sandbox_svc, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.experiment_sandbox_service.RUNS_ROOT",
        tmp_path / "runs",
    )
    csv_path = tmp_path / "hepar.csv"
    csv_path.write_text(
        "age;jaundice;carcinoma;fibrosis\n"
        "30;present;absent;1\n"
        "40;absent;present;0\n"
        "35;present;present;1\n"
        "50;absent;absent;0\n"
        "45;present;absent;1\n"
        "55;absent;present;0\n"
        "38;present;present;1\n"
        "42;absent;absent;0\n"
        "33;present;absent;1\n",
        encoding="utf-8",
    )
    spec = {
        "target_column": "carcinoma",
        "feature_columns": ["age", "jaundice", "fibrosis"],
        "baselines": ["Baseline", "Proposed"],
        "primary_metric": "accuracy",
        "task_type": "classification",
        "split_strategy": "train_test",
    }
    script = build_spec_validation_script(spec)
    result = sandbox_svc.execute_analysis_script(
        run_id="spec-val-test",
        analysis_script=script,
        csv_data_path=str(csv_path),
    )

    assert result["success"] is True, result.get("stderr") or result.get("stdout")
    assert result["output_complete"] is True
    metrics = result["metrics"]
    assert metrics.get("validation_mode") == "spec_aligned"
    assert metrics.get("target_column") == "carcinoma"
    assert metrics.get("baseline_score") is not None
    assert metrics.get("proposed_score") is not None
    assert not is_proxy_validation_metrics(metrics)
    alignment = assess_sandbox_spec_alignment(metrics, spec, sandbox=result)
    assert alignment["aligned"] is True


def test_assess_validation_readiness_blocks_inadequate():
    readiness = assess_validation_readiness(
        {
            "data_requirements": {
                "adequacy": {
                    "status": "inadequate",
                    "mismatch_reasons": ["FHIR 合规表无法验证联邦学习 F1"],
                }
            },
        },
        [{"columns": ["Indicator ID", "Score Rater A"], "data_type": "tabular"}],
    )
    assert readiness["blocked"] is True
    assert any("不匹配" in b for b in readiness["blockers"])


def test_result_verification_rejects_proxy_metrics():
    skill = ResultVerificationSkill()
    with patch("app.skills.experiment.result_verification_skill.qwen_structured_chat") as mock_llm:
        mock_llm.return_value = {
            "verified": True,
            "confidence": 0.9,
            "issues": [],
            "verification_summary": "ok",
        }
        result = asyncio.run(
            skill.run(
                input_data={
                    "hypothesis": "联邦学习 F1 提升",
                    "experiment_design": {"metrics": "f1"},
                    "preliminary_analysis": {"data_source_flag": "real_data"},
                    "has_real_data": 1,
                    "sandbox_execution": {
                        "success": True,
                        "output_complete": True,
                        "metrics": {
                            "data_source": "sandbox_default_script",
                            "encoded_value_column": "score",
                            "primary_metric": 0.5,
                        },
                        "plots": [{"plot_id": "experiment_result"}],
                    },
                    "spec_alignment": {"aligned": False, "reason": "代理指标"},
                },
                context={},
            )
        )
    assert result.data.get("verified") is False
    assert result.data.get("data_backed") is False


def test_small_validation_agent_no_pilot_fallback(monkeypatch, tmp_path):
    agent = SmallValidationAgent()
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "age;carcinoma\n1;0\n2;1\n3;0\n4;1\n5;0\n6;1\n7;0\n8;1\n",
        encoding="utf-8",
    )

    def fake_execute(*, run_id, analysis_script, csv_data_path, extra_env=None):
        return {
            "success": False,
            "output_complete": False,
            "metrics": {},
            "plots": [],
            "stderr": "script failed",
            "artifact_dir": str(tmp_path / "artifacts"),
        }

    monkeypatch.setattr(
        "app.agents.small_validation_agent.get_experiment_sandbox_service",
        lambda: type("S", (), {"execute_analysis_script": staticmethod(fake_execute)})(),
    )
    monkeypatch.setattr(agent, "_save_validation_files", lambda *a, **k: "vid")

    result = agent.generate_validation(
        hypothesis="验证 carcinoma 分类",
        csv_data_path=str(csv_path),
        experiment_design={
            "experiment_spec": {
                "target_column": "carcinoma",
                "feature_columns": ["age"],
                "primary_metric": "accuracy",
                "baselines": ["Baseline", "Proposed"],
            },
            "data_requirements": {"adequacy": {"status": "adequate"}},
        },
        run_id="run-no-pilot",
    )

    assert "pilot_analysis" not in result or not result.get("pilot_analysis")
    sb = result.get("sandbox_execution") or {}
    assert sb.get("pilot_fallback") is not True
