"""联邦结果分析 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


class FederatedResultAnalysisSkill(BaseSkill):
    name = "FederatedResultAnalysis"
    description = "分析联邦 pilot 结果并生成摘要"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        pilot = input_data.get("pilot_result", {}) or {}
        mode = pilot.get("execution_mode", "skipped")
        comparison: List[Dict[str, Any]] = pilot.get("metric_comparison", []) or []

        summary_lines: List[str] = []
        if mode == "uploaded_csv":
            summary_lines.append(f"基于上传 CSV 聚合分析，最佳方法: {pilot.get('best_method', 'N/A')}")
        elif mode == "simulation":
            summary_lines.append(
                f"使用 simulated pilot（明确标注 simulated），最佳方法: {pilot.get('best_method', 'N/A')}"
            )
        else:
            summary_lines.append("数据不足，已 skipped，未编造联邦训练结果")

        if comparison:
            top3 = comparison[:3]
            for item in top3:
                summary_lines.append(
                    f"- {item.get('method')}: acc={item.get('global_accuracy')}, "
                    f"f1={item.get('f1_score', 'N/A')}, comm={item.get('communication_cost_mb', 'N/A')}"
                )

        analysis = {
            "execution_mode": mode,
            "best_method": pilot.get("best_method", ""),
            "summary": "\n".join(summary_lines),
            "metric_comparison": comparison,
            "non_iid_sensitivity": pilot.get("non_iid_sensitivity", {}),
            "communication_efficiency": pilot.get("communication_efficiency", {}),
            "client_drift_analysis": pilot.get("client_drift_analysis", {}),
            "result_source": pilot.get("result_source", mode),
        }
        result.data = analysis
        return result
