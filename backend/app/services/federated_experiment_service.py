"""联邦学习实验编排服务"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.project_modes import (
    FL_KNOWN_REFERENCES,
    ProjectMode,
    empty_fl_context,
    normalize_project_mode,
)
from app.skills.federated_experiment.federated_data_schema_skill import FederatedDataSchemaSkill
from app.skills.federated_experiment.federated_experiment_plan_skill import FederatedExperimentPlanSkill
from app.skills.federated_experiment.federated_replanning_skill import FederatedReplanningSkill
from app.skills.federated_experiment.federated_result_analysis_skill import FederatedResultAnalysisSkill
from app.skills.federated_experiment.federated_simulation_executor_skill import FederatedSimulationExecutorSkill
from app.skills.federated_experiment.privacy_mechanism_suggestion_skill import PrivacyMechanismSuggestionSkill

logger = logging.getLogger(__name__)


class FederatedExperimentService:
    def __init__(self, db=None):
        self.db = db

    async def build_fl_context_from_columns(self, columns: List[str]) -> Dict[str, Any]:
        if not columns:
            return empty_fl_context()
        skill = FederatedDataSchemaSkill()
        res = await skill.run({"columns": columns}, {"stage": "federated_data_schema"})
        return res.data or empty_fl_context()

    def build_fl_context_from_data_context(self, data_context: Dict[str, Any]) -> Dict[str, Any]:
        all_columns: List[str] = []
        for ds in data_context.get("datasets", []) or []:
            all_columns.extend(ds.get("columns") or [])
        if data_context.get("fl_context"):
            return data_context["fl_context"]
        return asyncio.run(self.build_fl_context_from_columns(list(dict.fromkeys(all_columns))))

    async def build_experiment_plan(
        self,
        hypothesis: str,
        fl_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan_skill = FederatedExperimentPlanSkill()
        plan_res = await plan_skill.run(
            {
                "hypothesis": hypothesis,
                "fl_setting": fl_context.get("fl_setting", "unknown"),
                "fl_context": fl_context,
            },
            {"stage": "federated_experiment_plan"},
        )
        plan = plan_res.data or {}

        privacy_skill = PrivacyMechanismSuggestionSkill()
        privacy_res = await privacy_skill.run(
            {"fl_setting": fl_context.get("fl_setting"), "fl_context": fl_context},
            {"stage": "privacy_mechanism"},
        )
        plan["privacy_mechanisms"] = privacy_res.data.get("privacy_mechanisms", [])
        plan["skill_outputs"] = {
            "federated_experiment_plan": plan,
            "privacy_mechanism_suggestion": privacy_res.data,
        }
        return plan

    def build_experiment_design_result(
        self,
        hypothesis: str,
        fl_context: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        baselines = plan.get("baselines", [])
        metrics = plan.get("metrics", [])
        variables = plan.get("variables", [])
        privacy = plan.get("privacy_mechanisms", [])
        fl_setting = fl_context.get("fl_setting", "unknown")

        return {
            "methods": plan.get(
                "methods_summary",
                f"联邦学习 {fl_setting} 对比实验：{', '.join(baselines[:5])}",
            ),
            "datasets": (
                "Source：历史联邦实验 CSV、公开 FL benchmark（LEAF/FEMNIST）、组内标注报告。\n"
                "Target：客户端数据分布、特征方/标签方对齐数据、通信日志、privacy_budget 配置。"
            ),
            "source_data": "历史联邦实验数据、公开 FL benchmark、组内标注报告、客户端通信日志",
            "target_data": "客户端 Non-IID 分布、特征方/标签方数据、aligned_id 对齐样本、通信与 drift 指标",
            "baselines": "\n".join(f"- {b}" for b in baselines),
            "metrics": "\n".join(f"- {m}" for m in metrics),
            "experimental_steps": "\n".join(
                f"{i + 1}. {s}" for i, s in enumerate(plan.get("experimental_steps", []))
            ),
            "expected_results": (
                f"对比 {len(baselines)} 个联邦 baseline 在 {fl_setting} 场景下的精度、通信与 drift 表现"
            ),
            "limitations": (
                "Non-IID 划分、客户端参与率、通信带宽与 privacy_budget 会显著影响结论；"
                "需用真实 CSV 或 benchmark 验证 simulated pilot。"
            ),
            "skill_outputs": plan.get("skill_outputs", {}),
            "federated_plan": plan,
            "fl_context": fl_context,
            "fl_variables": variables,
            "privacy_mechanisms": privacy,
            "project_mode": ProjectMode.FEDERATED_LEARNING.value,
        }

    async def run_pilot_validation(
        self,
        datasets: List[Dict[str, Any]],
        fl_context: Dict[str, Any],
        experiment_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        exec_skill = FederatedSimulationExecutorSkill()
        exec_res = await exec_skill.run(
            {
                "datasets": datasets,
                "fl_context": fl_context,
                "experiment_plan": experiment_plan,
            },
            {"stage": "federated_simulation"},
        )
        pilot = exec_res.data or {"execution_mode": "skipped"}

        analysis_skill = FederatedResultAnalysisSkill()
        analysis_res = await analysis_skill.run({"pilot_result": pilot}, {"stage": "federated_analysis"})

        replan_skill = FederatedReplanningSkill()
        replan_res = await replan_skill.run(
            {
                "pilot_result": pilot,
                "fl_setting": fl_context.get("fl_setting"),
            },
            {"stage": "federated_replanning"},
        )

        return {
            **pilot,
            "analysis": analysis_res.data,
            "next_round_suggestions": replan_res.data.get("next_round_suggestions", []),
            "skill_outputs": {
                "federated_simulation_executor": pilot,
                "federated_result_analysis": analysis_res.data,
                "federated_replanning": replan_res.data,
            },
        }

    def enrich_report_sections(
        self,
        chapters: Dict[str, Any],
        fl_context: Dict[str, Any],
        experiment_design: Dict[str, Any],
        federated_pilot: Dict[str, Any],
    ) -> Dict[str, Any]:
        fl_setting = fl_context.get("fl_setting", "unknown")
        plan = experiment_design.get("federated_plan") or experiment_design.get("skill_outputs", {}).get(
            "federated_experiment_plan", {}
        )
        baselines = plan.get("baselines") or []
        mode = federated_pilot.get("execution_mode", "skipped")
        result_source = federated_pilot.get("result_source", mode)

        problem_extra = (
            f"\n\n【联邦学习场景】当前为 {fl_setting}。"
            "需关注 Non-IID 客户端分布、异构模型结构、通信成本、隐私保护（DP/PSI/Secure Aggregation）"
            "及 VFL 样本对齐（aligned_id / aligned_sample_rate）等问题。"
        )
        chapters["problem_statement"] = (chapters.get("problem_statement") or "") + problem_extra

        rationale_extra = (
            "\n\n【联邦推理链】基于 FedAvg/FedProx/SCAFFOLD 等横向 baseline，"
            "结合 FedMD/FedDF 知识蒸馏、SplitNN/VFL 与个性化联邦（FedPer/pFedMe/Ditto）"
            "分析 Non-IID 与 client drift 下的精度-通信权衡。"
        )
        chapters["rationale"] = (chapters.get("rationale") or "") + rationale_extra

        tech = chapters.get("technical_details") or ""
        tech_extra = (
            "\n\n【联邦技术细节】涉及 FedAvg、FedProx、SCAFFOLD、FedMD、FedDF、SplitNN、VFL、"
            "差分隐私（DP）、PSI 与 Secure Aggregation；"
            f"变量包括 num_clients、non_iid_degree、communication_rounds、privacy_budget 等。"
        )
        chapters["technical_details"] = tech + tech_extra

        datasets_text = chapters.get("datasets") or ""
        chapters["datasets"] = datasets_text + (
            "\n\nSource：历史联邦实验数据、公开 FL benchmark、组内标注报告。\n"
            "Target：客户端数据分布、特征方/标签方数据、通信日志、privacy_budget 配置。"
        )

        experiments = chapters.get("experiments") or ""
        if baselines:
            experiments += "\n\n【联邦 Baselines】\n" + "\n".join(f"- {b}" for b in baselines[:12])
        chapters["experiments"] = experiments

        results = chapters.get("results") or ""
        results += (
            f"\n\n【联邦 Pilot 结果】execution_mode={mode}；来源：{result_source}。"
            f" best_method={federated_pilot.get('best_method', 'N/A')}。"
        )
        if mode == "skipped":
            results += "\n证据链/数据不足，未编造联邦训练数值，需补充 CSV 后重跑。"
        chapters["results"] = results

        refs = chapters.get("references") or ""
        if refs and "FedAvg" not in refs:
            refs += "\n\n【联邦学习参考文献】\n" + "\n".join(f"- {r}" for r in FL_KNOWN_REFERENCES)
        elif not refs.strip():
            chapters["references"] = "\n".join(f"- {r}" for r in FL_KNOWN_REFERENCES)
        else:
            chapters["references"] = refs

        chapters["report_mode"] = ProjectMode.FEDERATED_LEARNING.value
        return chapters


def get_federated_experiment_service(db=None) -> FederatedExperimentService:
    return FederatedExperimentService(db)
