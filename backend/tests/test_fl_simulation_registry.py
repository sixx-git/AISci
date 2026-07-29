"""联邦仿真 registry / 门闩 / flower 兼容入口。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.execution_metadata import annotate_validation_execution_metadata
from app.core.project_modes import empty_fl_simulation_config, is_federated_learning_mode
from app.services.fl_simulation.registry import list_backend_capabilities, resolve_backend
from app.services.fl_simulation.runner import FlSimulationError, get_fl_simulation_runner
from app.services.fl_simulation.schemas import normalize_spec


def test_general_mode_rejected_by_runner():
    runner = get_fl_simulation_runner()
    with pytest.raises(FlSimulationError) as ei:
        runner.capabilities(project_mode="general")
    assert ei.value.code == "FL_MODE_REQUIRED"


def test_fl_mode_capabilities():
    caps = get_fl_simulation_runner().capabilities(project_mode="federated_learning")
    assert caps["enabled"] is True
    ids = {b["id"] for b in caps["backends"]}
    assert ids == {"local_pack", "flower", "fedml"}
    fedml = next(b for b in caps["backends"] if b["id"] == "fedml")
    assert fedml.get("enabled") is True
    assert "fallback" in fedml or fedml.get("installed") is True


def test_resolve_backends():
    assert resolve_backend("local_pack").backend_id == "local_pack"
    assert resolve_backend("flower").backend_id == "flower"
    assert resolve_backend("fedml").backend_id == "fedml"
    items = list_backend_capabilities()
    assert len(items) == 3


def test_normalize_spec_bounds():
    spec = normalize_spec({"num_clients": 1, "rounds": 9999, "backend": "flower"})
    assert spec.num_clients == 2
    assert spec.rounds == 200
    assert spec.backend == "flower"


def test_empty_fl_simulation_config():
    cfg = empty_fl_simulation_config(backend="flower", num_clients=8, rounds=12)
    assert cfg["backend"] == "flower"
    assert cfg["spec"]["num_clients"] == 8
    assert "单机" in cfg["note"]


def test_fedml_numpy_fallback_run(tmp_path: Path):
    backend = resolve_backend("fedml")
    result = backend.run(
        normalize_spec(
            {
                "backend": "fedml",
                "num_clients": 3,
                "rounds": 2,
                "strategy": "FedProx",
                "partition": "dirichlet",
                "timeout_sec": 60,
            }
        ),
        work_dir=tmp_path / "fedml",
    )
    assert result["execution_mode"] == "fedml"
    assert result["success"] is True
    assert result.get("framework") in ("fedml", "fedml_numpy_compat")
    assert "global_accuracy" in (result.get("metrics") or {})
    metrics_path = Path((result.get("artifacts") or {}).get("metrics_path") or "")
    assert metrics_path.is_file()
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert data["communication_rounds"] == 2
    assert data["method"] == "FedProx"


def test_fedml_disabled_returns_stub(tmp_path: Path, monkeypatch):
    from app.core import config as cfg_mod

    settings = cfg_mod.get_settings()
    monkeypatch.setattr(settings, "AISCI_FL_FEDML_ENABLED", False)
    backend = resolve_backend("fedml")
    result = backend.run(normalize_spec({"backend": "fedml"}), work_dir=tmp_path / "fedml_off")
    assert result["success"] is False
    assert result["execution_mode"] == "fedml_stub"


def test_flower_numpy_fallback_run(tmp_path: Path):
    backend = resolve_backend("flower")
    result = backend.run(
        normalize_spec(
            {
                "backend": "flower",
                "num_clients": 3,
                "rounds": 2,
                "strategy": "FedAvg",
                "partition": "iid",
                "timeout_sec": 60,
            }
        ),
        work_dir=tmp_path / "flower",
    )
    assert result["execution_mode"] == "flower"
    assert result["success"] is True
    assert "global_accuracy" in (result.get("metrics") or {})
    metrics_path = Path((result.get("artifacts") or {}).get("metrics_path") or "")
    assert metrics_path.is_file()
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert data["communication_rounds"] == 2


def test_local_pack_run_if_script_exists(tmp_path: Path):
    from app.services.fl_pack_service import fl_pack_root

    entry = fl_pack_root() / "scripts" / "run_fedavg_pilot.py"
    if not entry.is_file():
        pytest.skip("FL pack scripts missing")
    backend = resolve_backend("local_pack")
    result = backend.run(
        normalize_spec({"backend": "local_pack", "timeout_sec": 90}),
        work_dir=tmp_path / "local",
    )
    assert result["execution_mode"] == "local_pack"
    # success depends on sklearn env; just ensure contract keys
    assert "metrics" in result
    assert "artifacts" in result


def test_execution_metadata_ignores_federated_pilot_in_general():
    sv = {
        "federated_pilot": {"execution_mode": "flower"},
        "sandbox_execution": {"success": True, "return_code": 0},
    }
    out = annotate_validation_execution_metadata(sv, project_mode="general")
    assert out["execution_tier"] == "real_sandbox"
    assert "flower" not in str(out.get("execution_notes") or [])


def test_execution_metadata_flower_in_fl_mode():
    sv = {
        "federated_pilot": {
            "execution_mode": "flower",
            "framework_run": {"execution_mode": "flower", "success": True},
        }
    }
    out = annotate_validation_execution_metadata(sv, project_mode="federated_learning")
    assert out["execution_tier"] == "flower"
    assert is_federated_learning_mode("federated_learning")
