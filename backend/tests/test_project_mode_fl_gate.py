"""通用 vs 联邦模式门控：防止 FL 内容泄漏到 general。"""
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
