"""联邦实验计划 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import FL_METRICS, FL_VARIABLES
from app.skills.base import BaseSkill, SkillResult
from app.skills.federated_experiment.federated_baseline_selection_skill import (
    FederatedBaselineSelectionSkill,
)


class FederatedExperimentPlanSkill(BaseSkill):
    name = "FederatedExperimentPlan"
    description = "生成联邦实验 baselines/metrics/variables 计划"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        fl_setting = input_data.get("fl_setting", "horizontal_fl")
        hypothesis = input_data.get("hypothesis", "")
        fl_context = input_data.get("fl_context", {})

        baseline_skill = FederatedBaselineSelectionSkill()
        baseline_res = await baseline_skill.run({"fl_setting": fl_setting}, context)
        baselines = baseline_res.data.get("baselines", [])

        metrics = list(FL_METRICS)
        detected_metrics = fl_context.get("metrics_fields") or []
        if detected_metrics:
            metrics = list(dict.fromkeys(detected_metrics + metrics))

        variables = list(FL_VARIABLES)
        steps = [
            "划分客户端/参与方数据，标注 Non-IID 类型与程度",
            "配置 baseline（FedAvg/FedProx/SCAFFOLD 或 FedMD/FedDF/SplitNN/VFL）",
            "设定 local_epochs、参与率、通信轮次与隐私预算",
            "运行联邦训练并记录 global_accuracy、f1_score、communication_cost_mb、client_drift",
            "对比 baseline 并分析通信-精度权衡与公平性",
        ]

        plan = {
            "fl_setting": fl_setting,
            "hypothesis": hypothesis,
            "baselines": baselines,
            "metrics": metrics,
            "variables": variables,
            "experimental_steps": steps,
            "methods_summary": (
                f"针对 {fl_setting} 场景，对比 {', '.join(baselines[:6])} 等方法，"
                f"评估 {', '.join(metrics[:6])} 等指标。"
            ),
        }
        result.data = plan
        return result
