"""实验沙箱单元测试"""
import json
from pathlib import Path

import pytest

from app.services.experiment_sandbox_service import ExperimentSandboxService


@pytest.fixture
def sandbox_svc():
    return ExperimentSandboxService()


def test_execute_simple_script_writes_metrics_and_manifest(sandbox_svc, tmp_path, monkeypatch):
    run_id = "test-run-sandbox"
    monkeypatch.setattr(
        "app.services.experiment_sandbox_service.RUNS_ROOT",
        tmp_path / "runs",
    )

    script = """
from pathlib import Path
import json, os
out = Path(os.environ["AISCI_RUN_DIR"])
(out / "metrics.json").write_text(json.dumps({"accuracy": 0.91, "n": 42}), encoding="utf-8")
print('{"accuracy": 0.91}')
"""
    result = sandbox_svc.execute_analysis_script(
        run_id=run_id,
        analysis_script=script,
    )

    assert result["success"] is True
    assert result["metrics"].get("accuracy") == 0.91
    assert Path(result["manifest_path"]).exists()
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_id
    assert manifest["success"] is True


def test_execute_failed_script_returns_stderr(sandbox_svc, tmp_path, monkeypatch):
    run_id = "test-run-fail"
    monkeypatch.setattr(
        "app.services.experiment_sandbox_service.RUNS_ROOT",
        tmp_path / "runs",
    )

    result = sandbox_svc.execute_analysis_script(
        run_id=run_id,
        analysis_script="raise RuntimeError('boom')",
    )

    assert result["success"] is False
    assert result["return_code"] != 0
    assert result["data_source"] == "sandbox_failed"
