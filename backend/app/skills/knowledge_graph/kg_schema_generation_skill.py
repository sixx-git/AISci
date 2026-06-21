"""知识图谱 Schema 生成 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import ProjectMode, normalize_project_mode
from app.skills.base import BaseSkill, SkillResult

GENERAL_NODE_TYPES = [
    "Paper", "Method", "Dataset", "Metric", "Task", "Problem",
    "Hypothesis", "Evidence", "Result", "Limitation",
]

GENERAL_RELATION_TYPES = [
    "uses", "evaluates_on", "measured_by", "supports", "contradicts",
    "improves", "cites", "has_limitation", "requires_dataset",
]

FL_EXTRA_NODES = [
    "FedAlgorithm", "FLSetting", "Client", "Party", "AggregationMethod",
    "PrivacyMechanism", "NonIIDType", "CommunicationMetric", "DriftMetric", "Benchmark",
]

FL_EXTRA_RELATIONS = [
    "algorithm_handles_non_iid", "algorithm_reduces_drift", "algorithm_increases_comm_cost",
    "method_uses_privacy_mechanism", "vfl_requires_alignment", "dataset_simulates_client_distribution",
]


class KgSchemaGenerationSkill(BaseSkill):
    name = "KgSchemaGeneration"
    description = "按 project_mode 生成 KG schema"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        mode = normalize_project_mode(input_data.get("project_mode"))

        node_types = list(GENERAL_NODE_TYPES)
        relation_types = list(GENERAL_RELATION_TYPES)

        if mode == ProjectMode.FEDERATED_LEARNING.value:
            node_types.extend(FL_EXTRA_NODES)
            relation_types.extend(FL_EXTRA_RELATIONS)

        result.data = {
            "schema": {
                "node_types": node_types,
                "relation_types": relation_types,
                "project_mode": mode,
            }
        }
        return result
