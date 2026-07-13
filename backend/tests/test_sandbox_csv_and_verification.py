"""沙箱分号 CSV 读取与结果验证修复回归测试。"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.experiment_sandbox_service import ExperimentSandboxService
from app.services.tabular_encoding_utils import read_tabular_file
from app.skills.experiment.result_verification_skill import ResultVerificationSkill


@pytest.fixture
def sandbox_svc():
    return ExperimentSandboxService()


def test_read_tabular_file_semicolon(tmp_path):
    csv_path = tmp_path / "fhir_like.csv"
    csv_path.write_text(
        "carcinoma;jaundice;phosphatase\nabsent;present;a699_240\npresent;absent;a100_50\n",
        encoding="utf-8",
    )
    frame = read_tabular_file(str(csv_path))
    assert len(frame.columns) == 3
    assert "carcinoma" in frame.columns


def test_sandbox_executes_default_script_on_semicolon_csv(sandbox_svc, tmp_path, monkeypatch):
    from app.services.analysis_script_generator import default_analysis_script

    run_id = "test-semicolon-csv"
    monkeypatch.setattr(
        "app.services.experiment_sandbox_service.RUNS_ROOT",
        tmp_path / "runs",
    )
    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "carcinoma;jaundice;score\nabsent;present;1\npresent;absent;0\nabsent;absent;1\npresent;present;0\n",
        encoding="utf-8",
    )

    result = sandbox_svc.execute_analysis_script(
        run_id=run_id,
        analysis_script=default_analysis_script(),
        csv_data_path=str(csv_path),
    )

    assert result["success"] is True, result.get("stderr") or result.get("stdout")
    assert result["output_complete"] is True
    assert len(result.get("plots") or []) >= 1
    assert result["metrics"].get("primary_metric") is not None
    assert "note" not in result["metrics"] or result["metrics"].get("note") != "no metrics emitted"


def test_result_verification_accepts_sandbox_output():
    import asyncio

    skill = ResultVerificationSkill()
    with patch("app.skills.experiment.result_verification_skill.qwen_structured_chat") as mock_llm:
        mock_llm.return_value = {
            "verified": True,
            "confidence": 0.8,
            "issues": [],
            "verification_summary": "沙箱产出有效指标",
        }
        result = asyncio.run(
            skill.run(
                input_data={
                    "hypothesis": "test hypothesis",
                    "experiment_design": {"metrics": "f1 accuracy"},
                    "preliminary_analysis": {"data_source_flag": "no_data"},
                    "has_real_data": 1,
                    "sandbox_execution": {
                        "success": True,
                        "output_complete": True,
                        "metrics": {"primary_metric": 0.82, "f1": 0.75},
                        "plots": [{"plot_id": "experiment_result"}],
                    },
                },
                context={},
            )
        )
    assert result.data.get("data_backed") is True
    assert result.data.get("verified") is True
    assert not any("无真实数据" in w for w in (result.warnings or []))
