"""联邦 Baseline 选择 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import FL_BASELINES
from app.skills.base import BaseSkill, SkillResult


class FederatedBaselineSelectionSkill(BaseSkill):
    name = "FederatedBaselineSelection"
    description = "按联邦场景选择 baseline 方法"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        fl_setting = input_data.get("fl_setting", "horizontal_fl")

        baselines: List[str] = []
        if fl_setting in FL_BASELINES:
            baselines.extend(FL_BASELINES[fl_setting])
        else:
            baselines.extend(FL_BASELINES["horizontal_fl"])

        if fl_setting == "vertical_fl":
            dedup = list(dict.fromkeys(baselines))
            result.data = {"baselines": dedup, "fl_setting": fl_setting}
            return result

        if fl_setting != "personalized_fl":
            baselines.extend(FL_BASELINES["personalized_fl"][:3])
        if fl_setting not in ("vertical_fl", "heterogeneous_fl"):
            baselines.extend(FL_BASELINES["heterogeneous_fl"][:2])

        dedup: List[str] = []
        seen = set()
        for b in baselines:
            if b not in seen:
                seen.add(b)
                dedup.append(b)

        result.data = {"baselines": dedup, "fl_setting": fl_setting}
        return result
