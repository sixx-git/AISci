"""联邦场景识别 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import (
    HETEROGENEOUS_FL_FIELDS,
    HORIZONTAL_FL_FIELDS,
    VERTICAL_FL_FIELDS,
)
from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment._utils import match_fields


class FederatedScenarioRecognitionSkill(BaseSkill):
    name = "FederatedScenarioRecognition"
    description = "识别横向/异构/垂直/个性化联邦场景"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        columns: List[str] = input_data.get("columns", []) or []

        h = match_fields(columns, HORIZONTAL_FL_FIELDS)
        het = match_fields(columns, HETEROGENEOUS_FL_FIELDS)
        v = match_fields(columns, VERTICAL_FL_FIELDS)

        scores = {
            "horizontal_fl": len(h),
            "heterogeneous_fl": len(het),
            "vertical_fl": len(v),
            "personalized_fl": len(h) + (1 if "method" in [c.lower() for c in h] else 0),
        }
        fl_setting = max(scores, key=scores.get)
        if scores[fl_setting] == 0:
            fl_setting = "unknown"

        if fl_setting == "personalized_fl" and scores["horizontal_fl"] >= 3:
            fl_setting = "horizontal_fl" if scores["heterogeneous_fl"] < 2 else "heterogeneous_fl"

        result.data = {
            "fl_setting": fl_setting,
            "scores": scores,
            "horizontal_hits": h,
            "heterogeneous_hits": het,
            "vertical_hits": v,
        }
        return result
