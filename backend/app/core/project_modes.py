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


PROJECT_MODE_LABELS = {
    ProjectMode.GENERAL.value: "General AI Scientist",
    ProjectMode.FEDERATED_LEARNING.value: "Federated Learning (Starter Pack)",
}

PROJECT_MODE_LABELS_ZH = {
    ProjectMode.GENERAL.value: "通用 AI Scientist 模式",
    ProjectMode.FEDERATED_LEARNING.value: "联邦学习（资源包）模式",
}


def get_research_question_template(mode: str, scenario: str | None = None) -> Dict[str, str]:
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
