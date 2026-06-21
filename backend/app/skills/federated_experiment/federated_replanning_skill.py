"""联邦实验重规划 Skill — 结构化可验证 replan actions"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.iterative_science import build_structured_replan_actions
from app.skills.base import BaseSkill, SkillResult


class FederatedReplanningSkill(BaseSkill):
    name = "FederatedReplanning"
    description = "根据 pilot 结果给出可验证的结构化下一轮实验 actions"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        pilot = input_data.get("pilot_result", {}) or {}
        fl_setting = input_data.get("fl_setting", "horizontal_fl")
        fl_context = input_data.get("fl_context") or {"fl_setting": fl_setting}
        analysis = input_data.get("analysis") or {}

        actions = build_structured_replan_actions(pilot, fl_context, analysis)

        suggestions: List[str] = list(pilot.get("next_round_suggestions") or [])
        for act in actions:
            line = (
                f"[{act.get('priority')}] {act.get('action_id')}: "
                f"{act.get('parameter')}→{act.get('to_value')} "
                f"(验收: {act.get('expected_check')})"
            )
            suggestions.append(line)

        if not suggestions and pilot.get("execution_mode") == "skipped":
            if fl_setting == "vertical_fl":
                suggestions = [
                    "上传含 party_id/entity_id/feature_owner/label_owner/label 的 VFL CSV",
                    "确保 entity_id 对齐覆盖率 ≥ 85% 后再进入训练仿真",
                ]
            else:
                suggestions = [
                    "上传含 method、global_accuracy、f1_score、communication_cost_mb 的 CSV",
                    "或导入 LEAF/FEMNIST 等公开 FL benchmark 结果",
                ]

        dedup_s: List[str] = []
        seen = set()
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                dedup_s.append(s)

        result.data = {
            "next_round_suggestions": dedup_s[:10],
            "replan_actions": actions,
            "action_count": len(actions),
            "has_critical_actions": any(a.get("priority") == "critical" for a in actions),
        }
        return result
