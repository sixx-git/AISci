"""联邦实验计划 Skill — 含 VFL 垂直联邦专项计划"""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.project_modes import FL_METRICS, FL_VARIABLES, VFL_METRICS, VFL_VARIABLES
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

        if fl_setting == "vertical_fl":
            metrics = list(VFL_METRICS)
            detected_metrics = fl_context.get("metrics_candidates") or fl_context.get("metrics_fields") or []
            if detected_metrics:
                metrics = list(dict.fromkeys(detected_metrics + metrics))
            variables = list(VFL_VARIABLES)
            steps = [
                "确认特征方/标签方划分（feature_owner / label_owner）与 entity_id 对齐键",
                "执行 PSI 或 aligned_id 样本对齐，记录 alignment_success_rate 与 aligned_sample_rate",
                "配置 privacy_budget 与 Secure Aggregation / 差分隐私机制",
                "对比 Centralized Training、Local Only、SplitNN、VFL-LR、VFL-NN、FedBCD、SecureBoost",
                "记录 accuracy/F1/AUC、communication_cost、inference_latency、privacy_leakage_risk",
                "根据 pilot 结果调整特征方数量、对齐比例与通信轮次（闭环 replan）",
            ]
            verifiable_checks = [
                "alignment_success_rate >= 0.85 方可进入训练仿真",
                "VFL 方法 prediction_accuracy 优于 Local Only",
                "privacy_leakage_risk 不高于预设上限",
            ]
            methods_summary = (
                f"垂直联邦学习（VFL）场景：在样本对齐与隐私约束下，"
                f"对比 {', '.join(baselines[:7])}；"
                f"评估 {', '.join(metrics[:7])}；"
                f"变量含 num_feature_parties、aligned_sample_rate、privacy_budget 等。"
            )
        else:
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
            methods_summary = (
                f"针对 {fl_setting} 场景，对比 {', '.join(baselines[:6])} 等方法，"
                f"评估 {', '.join(metrics[:6])} 等指标。"
            )
            verifiable_checks = [
                "global_accuracy 相对 Local Only 有可量化提升",
                "communication_cost_mb 与 client_drift 可复现记录",
                "pilot CSV 或 simulation 明确标注 result_source",
            ]

        plan = {
            "fl_setting": fl_setting,
            "hypothesis": hypothesis,
            "baselines": baselines,
            "metrics": metrics,
            "variables": variables,
            "experimental_steps": steps,
            "methods_summary": methods_summary,
            "verifiable_checks": verifiable_checks,
        }
        result.data = plan
        return result
