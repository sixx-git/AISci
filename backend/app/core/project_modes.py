"""项目运行模式定义（仅保留通用模式；历史 federated_learning 回落为 general）。"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class ProjectMode(str, Enum):
    GENERAL = "general"


VALID_PROJECT_MODES = {ProjectMode.GENERAL.value}


def normalize_project_mode(mode: str | None) -> str:
    """非法或已淘汰模式（含历史 federated_learning）一律回落 general。"""
    if mode and mode in VALID_PROJECT_MODES:
        return mode
    return ProjectMode.GENERAL.value


PROJECT_MODE_LABELS = {
    ProjectMode.GENERAL.value: "General AI Scientist",
}

PROJECT_MODE_LABELS_ZH = {
    ProjectMode.GENERAL.value: "通用 AI Scientist 模式",
}


def get_research_question_template(mode: str, scenario: str | None = None) -> Dict[str, str]:
    return {}


def empty_fl_context() -> Dict[str, Any]:
    """兼容旧调用点：返回空结构（不再注入联邦字段）。"""
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
