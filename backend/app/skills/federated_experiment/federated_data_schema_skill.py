"""联邦数据 Schema 识别 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import (
    FL_METRICS_FIELDS,
    HETEROGENEOUS_FL_FIELDS,
    HORIZONTAL_FL_FIELDS,
    VERTICAL_FL_FIELDS,
    ProjectMode,
)
from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment._utils import match_fields, unique_preserve
from app.skills.federated_experiment.federated_scenario_recognition_skill import (
    FederatedScenarioRecognitionSkill,
)


class FederatedDataSchemaSkill(BaseSkill):
    name = "FederatedDataSchema"
    description = "识别联邦实验 CSV 字段结构"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        columns: List[str] = input_data.get("columns", []) or []

        scenario_skill = FederatedScenarioRecognitionSkill()
        scenario_res = await scenario_skill.run({"columns": columns}, context)
        fl_setting = scenario_res.data.get("fl_setting", "unknown")

        client_fields = unique_preserve(
            match_fields(columns, HORIZONTAL_FL_FIELDS + HETEROGENEOUS_FL_FIELDS)
        )
        party_fields = unique_preserve(match_fields(columns, VERTICAL_FL_FIELDS))
        metrics_fields = unique_preserve(match_fields(columns, FL_METRICS_FIELDS))
        detected_fields = unique_preserve(client_fields + party_fields + metrics_fields)

        target_candidates = metrics_fields[:]
        for pref in ("global_accuracy", "f1_score", "accuracy", "auc"):
            for col in columns:
                if col.lower().replace(" ", "_") == pref and col not in target_candidates:
                    target_candidates.insert(0, col)

        payload = {
            "project_mode": ProjectMode.FEDERATED_LEARNING.value,
            "fl_setting": fl_setting,
            "detected_fields": detected_fields,
            "client_fields": client_fields,
            "party_fields": party_fields,
            "metrics_fields": metrics_fields,
            "target_candidates": target_candidates[:10],
        }
        result.data = payload
        return result
