"""通用 vs 联邦模式门控：防止 FL 内容泄漏到 general。"""
import pytest

from app.core.project_modes import is_federated_learning_mode, normalize_project_mode
from app.services.validation_data_guidance_service import _domain_hint_datasets


def test_is_federated_learning_mode():
    assert is_federated_learning_mode("federated_learning") is True
    assert is_federated_learning_mode("general") is False
    assert is_federated_learning_mode(None) is False
    assert normalize_project_mode("bogus") == "general"


def test_domain_hints_exclude_fl_pack_in_general_mode():
    hyp = "在 Non-IID 客户端上比较 FedAvg 与 FedProx"
    general = _domain_hint_datasets(hyp, "FedAvg", "accuracy", project_mode="general")
    assert not any(h.get("role") == "fl_pack" for h in general)
    assert not any("LEAF" in str(h.get("dataset_name") or "") for h in general)


def test_domain_hints_allow_federated_in_fl_mode():
    hyp = "在 Non-IID 客户端上比较 FedAvg 与 FedProx"
    fl = _domain_hint_datasets(hyp, "FedAvg", "accuracy", project_mode="federated_learning")
    assert any(
        h.get("role") == "fl_pack" or "LEAF" in str(h.get("dataset_name") or "")
        for h in fl
    )


def test_fl_simulation_gate_rejects_general():
    from app.services.fl_simulation.runner import FlSimulationError, get_fl_simulation_runner

    with pytest.raises(FlSimulationError):
        get_fl_simulation_runner().run(
            project_mode="general",
            project_id="p-gen",
            experiment_id="e1",
            spec_raw={"backend": "flower"},
        )


def test_fl_simulation_gate_allows_fl_mode(tmp_path, monkeypatch):
    from app.services.fl_simulation import get_fl_simulation_runner
    from app.services import fl_simulation as fl_sim_pkg

    runner = get_fl_simulation_runner()
    monkeypatch.setattr(fl_sim_pkg.runner, "RUNS_ROOT", tmp_path)
    result = runner.run(
        project_mode="federated_learning",
        project_id="p-fl",
        experiment_id="e1",
        spec_raw={
            "backend": "flower",
            "num_clients": 3,
            "rounds": 2,
            "partition": "iid",
            "timeout_sec": 60,
        },
    )
    assert result["execution_mode"] == "flower"
    assert result["success"] is True
