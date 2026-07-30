"""项目运行模式：general + federated_learning（Starter Pack，非多机 runtime）。"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class ProjectMode(str, Enum):
    GENERAL = "general"
    FEDERATED_LEARNING = "federated_learning"


VALID_PROJECT_MODES = {
    ProjectMode.GENERAL.value,
    ProjectMode.FEDERATED_LEARNING.value,
}


def normalize_project_mode(mode: str | None) -> str:
    """非法模式回落 general；federated_learning 表示挂载 FL 资源包。"""
    if mode and mode in VALID_PROJECT_MODES:
        return mode
    return ProjectMode.GENERAL.value


def is_federated_learning_mode(mode: str | None) -> bool:
    """是否为联邦学习（资源包）项目模式。"""
    return normalize_project_mode(mode) == ProjectMode.FEDERATED_LEARNING.value


PROJECT_MODE_LABELS = {
    ProjectMode.GENERAL.value: "General AI Scientist",
    ProjectMode.FEDERATED_LEARNING.value: "Federated Learning (Starter Pack)",
}

PROJECT_MODE_LABELS_ZH = {
    ProjectMode.GENERAL.value: "通用 AI Scientist 模式",
    ProjectMode.FEDERATED_LEARNING.value: "联邦学习（资源包）模式",
}

# 联邦仿真后端（仅 federated_learning；与通用沙箱隔离）
FL_SIM_BACKENDS = ("local_pack", "flower", "fedml")
FL_SIM_BACKEND_LABELS = {
    "local_pack": "FL Pack 本地 pilot（sklearn）",
    "flower": "Flower 单机仿真",
    "fedml": "FedML 单机仿真",
}
FL_SIM_STRATEGIES = ("FedAvg", "FedProx")
FL_SIM_PARTITIONS = ("dirichlet", "iid", "pathological")


def empty_fl_simulation_config(
    *,
    backend: str = "local_pack",
    num_clients: int = 5,
    rounds: int = 10,
    strategy: str = "FedAvg",
    partition: str = "dirichlet",
) -> Dict[str, Any]:
    """写入 project.config.fl_simulation 的默认骨架。"""
    b = backend if backend in FL_SIM_BACKENDS else "local_pack"
    return {
        "enabled": True,
        "backend": b,
        "backend_label": FL_SIM_BACKEND_LABELS.get(b, b),
        "spec": {
            "num_clients": max(2, min(int(num_clients or 5), 50)),
            "rounds": max(1, min(int(rounds or 10), 200)),
            "strategy": strategy if strategy in FL_SIM_STRATEGIES else "FedAvg",
            "partition": partition if partition in FL_SIM_PARTITIONS else "dirichlet",
            "timeout_sec": 120,
        },
        "note": "单机进程内仿真，非多机真实联邦部署",
    }


def normalize_fl_sim_backend(backend: str | None, default: str = "local_pack") -> str:
    if backend and backend in FL_SIM_BACKENDS:
        return backend
    return default if default in FL_SIM_BACKENDS else "local_pack"


def get_research_question_template(mode: str, scenario: str | None = None) -> Dict[str, str]:
    """可选「建议填充」文案；创建项目不再自动写入。当前无调用方，保留供未来显式建议 API。"""
    if normalize_project_mode(mode) != ProjectMode.FEDERATED_LEARNING.value:
        return {}
    sc = (scenario or "hfl").lower()
    if sc in ("vfl", "vertical", "vertical_fl"):
        return {
            "research_question": (
                "在样本对齐与隐私约束下，垂直联邦（特征分区）能否在不共享原始特征的前提下"
                "达到接近集中训练的预测性能？"
            ),
            "research_domain": "垂直联邦学习 / VFL",
            "hint": "请明确对齐键、特征方与标签方、主指标（alignment_rate / AUC）。",
        }
    return {
        "research_question": (
            "在 Non-IID 客户端划分与通信预算约束下，FedAvg（或 FedProx）相对本地训练"
            "能否提升全局泛化并控制通信轮次？"
        ),
        "research_domain": "横向联邦学习 / HFL",
        "hint": "请明确客户端数、Non-IID 类型、global_accuracy 与 communication_rounds。",
    }


def empty_fl_context() -> Dict[str, Any]:
    """FL 上下文字段骨架（由列名规则或资源包填充）。"""
    return {
        "project_mode": ProjectMode.GENERAL.value,
        "fl_setting": "unknown",
        "federated_setting": "unknown",
        "detected_fields": [],
        "client_fields": [],
        "party_fields": [],
        "metrics_fields": [],
        "target_candidates": [],
        "metrics_candidates": [],
        "parties": [],
        "feature_parties": [],
        "label_party": "",
        "alignment_keys": [],
        "privacy_fields": [],
    }


def empty_vfl_context() -> Dict[str, Any]:
    return empty_fl_context()
