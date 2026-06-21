"""联邦实验重规划 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class FederatedReplanningSkill(BaseSkill):
    name = "FederatedReplanning"
    description = "根据 pilot 结果给出下一轮实验建议"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        pilot = input_data.get("pilot_result", {}) or {}
        fl_setting = input_data.get("fl_setting", "horizontal_fl")
        mode = pilot.get("execution_mode", "skipped")
        best = pilot.get("best_method", "")

        suggestions: List[str] = list(pilot.get("next_round_suggestions") or [])

        if mode == "skipped":
            suggestions = [
                "上传含 method、global_accuracy、f1_score、communication_cost_mb、client_drift 的 CSV",
                "或导入 LEAF/FEMNIST 等公开 FL benchmark 结果",
            ]
        elif mode == "simulation":
            suggestions.append("将 simulated pilot 替换为真实客户端实验日志")
        elif best:
            suggestions.append(f"围绕 {best} 调整 non_iid_degree 与 participation_rate 做敏感性分析")

        if fl_setting == "heterogeneous_fl":
            suggestions.append("增加 FedMD/FedDF 与 distillation_temperature 网格搜索")
        elif fl_setting == "vertical_fl":
            suggestions.append("评估 aligned_sample_rate 与 SplitNN/VFL baseline")

        dedup: List[str] = []
        seen = set()
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                dedup.append(s)

        result.data = {"next_round_suggestions": dedup[:8]}
        return result
