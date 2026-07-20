"""数据场景预设 — 将 project_mode 映射到 schema 对齐策略"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.data_finder._utils import FL_STANDARD_COLUMNS, GENERAL_STANDARD_COLUMNS


def project_mode_to_scenario(project_mode: str | None) -> str:
    mode = (project_mode or "").strip().lower()
    if mode == "federated_learning":
        return "federated_learning"
    if mode in ("ml_benchmark", "ml"):
        return "ml_benchmark"
    return "general"


def get_standard_columns_for_scenario(
    scenario: str,
    data_spec: Dict[str, Any] | None = None,
) -> List[str]:
    """按场景与 DataSpec 生成对齐用标准列列表。"""
    spec = data_spec or {}
    dynamic: List[str] = []
    for key in ("entities_of_interest", "target_variables"):
        for item in spec.get(key) or []:
            if item and item not in dynamic:
                dynamic.append(str(item))

    if scenario == "federated_learning":
        return list(dict.fromkeys(FL_STANDARD_COLUMNS + dynamic))

    if scenario == "ml_benchmark":
        return list(dict.fromkeys(GENERAL_STANDARD_COLUMNS + dynamic))

    # general：以 DataSpec 为主，ML 列作弱提示
    if dynamic:
        return list(dict.fromkeys(dynamic + GENERAL_STANDARD_COLUMNS))
    return list(GENERAL_STANDARD_COLUMNS)


def get_entity_column_hints(
    scenario: str,
    data_spec: Dict[str, Any] | None = None,
) -> List[str]:
    """实体解析用的列名提示（顺序优先）。"""
    spec = data_spec or {}
    hints = [str(x) for x in (spec.get("entities_of_interest") or []) if x]

    if scenario == "federated_learning":
        hints.extend([
            "entity_id", "client_id", "party_id", "aligned_id",
            "sample_id", "subject_id", "id",
        ])
    else:
        hints.extend([
            "entity_id", "sample_id", "subject_id", "patient_id",
            "specimen_id", "record_id", "id", "name",
        ])
    return list(dict.fromkeys(hints))


def get_column_synonyms(data_spec: Dict[str, Any] | None) -> Dict[str, List[str]]:
    spec = data_spec or {}
    raw = spec.get("column_synonyms") or {}
    out: Dict[str, List[str]] = {}
    for std, syns in raw.items():
        if isinstance(syns, list):
            out[str(std)] = [str(s) for s in syns]
        elif isinstance(syns, str):
            out[str(std)] = [syns]
    return out


def scenario_label(scenario: str) -> str:
    labels = {
        "general": "通用多领域",
        "ml_benchmark": "ML Benchmark",
        "federated_learning": "联邦学习",
    }
    return labels.get(scenario, scenario)
