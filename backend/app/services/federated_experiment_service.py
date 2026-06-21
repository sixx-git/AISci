"""联邦学习实验编排服务"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.iterative_science import (
    append_subsections_to_chapter,
    build_campaign_lineage_text,
    build_verifiable_hypothesis_spec,
    compute_pareto_frontier,
    compute_pareto_frontier_3d,
)
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

    async def build_fl_context_from_columns(
        self,
        columns: List[str],
        datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not columns:
            return empty_fl_context()
        skill = FederatedDataSchemaSkill()
        res = await skill.run(
            {"columns": columns, "datasets": datasets or []},
            {"stage": "federated_data_schema"},
        )
        return res.data or empty_fl_context()

    def build_fl_context_from_data_context(self, data_context: Dict[str, Any]) -> Dict[str, Any]:
        all_columns: List[str] = []
        datasets = data_context.get("datasets", []) or []
        for ds in datasets:
            all_columns.extend(ds.get("columns") or [])
        if data_context.get("fl_context") and data_context["fl_context"].get("fl_setting") != "unknown":
            merged = dict(data_context["fl_context"])
            merged.setdefault("federated_setting", merged.get("fl_setting", "unknown"))
            return merged
        return asyncio.run(
            self.build_fl_context_from_columns(list(dict.fromkeys(all_columns)), datasets)
        )

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

    def apply_campaign_feedback(
        self,
        plan: Dict[str, Any],
        validation_feedback: Optional[List[str]] = None,
        replan_actions: Optional[List[Dict[str, Any]]] = None,
        campaign_round: int = 2,
    ) -> Dict[str, Any]:
        """将上一轮 pilot/replan 反馈注入实验计划（Campaign R2+）。"""
        updated = dict(plan)
        steps = list(updated.get("experimental_steps") or [])
        feedback = list(validation_feedback or [])
        actions = list(replan_actions or [])

        if campaign_round > 1:
            steps.insert(0, f"【Campaign R{campaign_round}】依据上一轮 pilot replan actions 修订实验变量与 baseline 优先级")

        for act in actions[:4]:
            param = act.get("parameter", "")
            to_val = act.get("to_value", "")
            check = act.get("expected_check", "")
            steps.append(
                f"执行 replan `{act.get('action_id')}`：调整 {param}→{to_val}；验收 {check}"
            )

        for note in feedback[:4]:
            if note not in str(steps):
                steps.append(f"反馈约束：{note}")

        updated["experimental_steps"] = steps[:12]
        suffix = f"（Campaign R{campaign_round} 已注入 {len(actions)} 条 replan）"
        updated["methods_summary"] = (updated.get("methods_summary") or "") + suffix
        updated["campaign_round"] = campaign_round
        updated["injected_replan_actions"] = actions[:6]
        return updated

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
        is_vfl = fl_setting == "vertical_fl"

        if is_vfl:
            source_data = (
                "历史多方特征 CSV（party_id/entity_id/feature_owner）、"
                "人工标注报告、已有 VFL/联邦实验数据、对齐日志"
            )
            target_data = (
                "拟采集的多方特征表、entity_id/aligned_id 样本对齐信息、"
                "privacy_budget 与 communication_round 配置、标签方标注"
            )
            datasets_text = (
                "Source：历史多方特征、人工标注报告、已有联邦/VFL 实验 CSV。\n"
                "Target：多方特征表、样本对齐表（PSI/aligned_id）、隐私约束参数。"
            )
            limitations = (
                "样本对齐成功率、特征缺失率、privacy_budget 与通信轮次显著影响 VFL 结论；"
                "需用含 party_id/entity_id/feature_owner/label_owner 的真实 CSV 验证 pilot。"
            )
        else:
            source_data = "历史联邦实验数据、公开 FL benchmark、组内标注报告、客户端通信日志"
            target_data = "客户端 Non-IID 分布、特征方/标签方数据、aligned_id 对齐样本、通信与 drift 指标"
            datasets_text = (
                "Source：历史联邦实验 CSV、公开 FL benchmark（LEAF/FEMNIST）、组内标注报告。\n"
                "Target：客户端数据分布、特征方/标签方对齐数据、通信日志、privacy_budget 配置。"
            )
            limitations = (
                "Non-IID 划分、客户端参与率、通信带宽与 privacy_budget 会显著影响结论；"
                "需用真实 CSV 或 benchmark 验证 simulated pilot。"
            )

        verifiable = build_verifiable_hypothesis_spec(hypothesis, plan, fl_context)

        return {
            "hypothesis": hypothesis,
            "methods": plan.get(
                "methods_summary",
                f"联邦学习 {fl_setting} 对比实验：{', '.join(baselines[:5])}",
            ),
            "datasets": datasets_text,
            "source_data": source_data,
            "target_data": target_data,
            "baselines": "\n".join(f"- {b}" for b in baselines),
            "metrics": "\n".join(f"- {m}" for m in metrics),
            "experimental_steps": "\n".join(
                f"{i + 1}. {s}" for i, s in enumerate(plan.get("experimental_steps", []))
            ),
            "expected_results": (
                f"对比 {len(baselines)} 个{' VFL ' if is_vfl else '联邦 '}baseline 在 {fl_setting} 场景下的"
                f"精度、通信与{'对齐/隐私' if is_vfl else 'drift'} 表现"
            ),
            "limitations": limitations,
            "skill_outputs": plan.get("skill_outputs", {}),
            "federated_plan": plan,
            "fl_context": fl_context,
            "fl_variables": variables,
            "privacy_mechanisms": privacy,
            "verifiable_hypothesis": verifiable,
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
        analysis_data = analysis_res.data or {}
        pareto = compute_pareto_frontier(pilot.get("metric_comparison") or [])
        pareto_3d = compute_pareto_frontier_3d(pilot.get("metric_comparison") or [])
        analysis_data["pareto_frontier"] = pareto
        analysis_data["pareto_frontier_3d"] = pareto_3d

        replan_skill = FederatedReplanningSkill()
        replan_res = await replan_skill.run(
            {
                "pilot_result": pilot,
                "fl_setting": fl_context.get("fl_setting"),
                "fl_context": fl_context,
                "analysis": analysis_res.data,
            },
            {"stage": "federated_replanning"},
        )
        replan_data = replan_res.data or {}

        return {
            **pilot,
            "analysis": analysis_data,
            "next_round_suggestions": replan_data.get("next_round_suggestions", []),
            "replan_actions": replan_data.get("replan_actions", []),
            "pareto_frontier": pareto,
            "pareto_frontier_3d": pareto_3d,
            "skill_outputs": {
                "federated_simulation_executor": pilot,
                "federated_result_analysis": analysis_data,
                "federated_replanning": replan_data,
            },
        }

    def enrich_report_sections(
        self,
        chapters: Dict[str, Any],
        fl_context: Dict[str, Any],
        experiment_design: Dict[str, Any],
        federated_pilot: Dict[str, Any],
        iteration_snapshots: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        fl_setting = fl_context.get("fl_setting", "unknown")
        is_vfl = fl_setting == "vertical_fl"
        plan = experiment_design.get("federated_plan") or experiment_design.get("skill_outputs", {}).get(
            "federated_experiment_plan", {}
        )
        baselines = plan.get("baselines") or []
        mode = federated_pilot.get("execution_mode", "skipped")
        result_source = federated_pilot.get("result_source", mode)

        if is_vfl:
            problem_extra = (
                "\n\n【垂直联邦学习（VFL）场景】本研究属于纵向特征融合设定："
                "特征分布在不同参与方（特征方 feature parties），标签集中在标签方（label party）；"
                "需在 entity_id/aligned_id 样本对齐与 privacy_budget 隐私保护约束下进行协同建模，"
                "权衡 prediction_accuracy、communication_cost 与 privacy_leakage_risk。"
            )
            rationale_extra = (
                "\n\n【VFL 推理链】基于 SplitNN/VFL-LR/VFL-NN 与 SecureBoost/FedBCD，"
                "结合 PSI 样本对齐、Secure Aggregation 与差分隐私（DP），"
                "分析多方异构特征融合下的精度-通信-隐私权衡。"
            )
            tech_extra = (
                "\n\n【VFL 技术细节】必须涵盖：PSI / 样本对齐（entity_id、aligned_id）、"
                "Secure Aggregation、Differential Privacy、Split Learning / VFL；"
                "调用 Qwen / 通义千问 / 阿里云百炼 进行任务规划与报告生成；"
                "变量包括 num_feature_parties、aligned_sample_rate、privacy_budget、"
                "feature_missing_rate、communication_rounds、inference_latency。"
            )
            datasets_extra = (
                "\n\nSource：历史多方特征 CSV、人工标注报告、已有 VFL/联邦实验数据。\n"
                "Target：多方特征表、样本对齐信息（aligned_id）、privacy_budget 与通信配置。"
            )
        else:
            problem_extra = (
                f"\n\n【联邦学习场景】当前为 {fl_setting}。"
                "需关注 Non-IID 客户端分布、异构模型结构、通信成本、隐私保护（DP/PSI/Secure Aggregation）"
                "及 VFL 样本对齐（aligned_id / aligned_sample_rate）等问题。"
            )
            rationale_extra = (
                "\n\n【联邦推理链】基于 FedAvg/FedProx/SCAFFOLD 等横向 baseline，"
                "结合 FedMD/FedDF 知识蒸馏、SplitNN/VFL 与个性化联邦（FedPer/pFedMe/Ditto）"
                "分析 Non-IID 与 client drift 下的精度-通信权衡。"
            )
            tech_extra = (
                "\n\n【联邦技术细节】涉及 FedAvg、FedProx、SCAFFOLD、FedMD、FedDF、SplitNN、VFL、"
                "差分隐私（DP）、PSI 与 Secure Aggregation；"
                f"变量包括 num_clients、non_iid_degree、communication_rounds、privacy_budget 等。"
            )
            datasets_extra = (
                "\n\nSource：历史联邦实验数据、公开 FL benchmark、组内标注报告。\n"
                "Target：客户端数据分布、特征方/标签方数据、通信日志、privacy_budget 配置。"
            )

        chapters["problem_statement"] = (chapters.get("problem_statement") or "") + problem_extra
        chapters["rationale"] = (chapters.get("rationale") or "") + rationale_extra

        tech = chapters.get("technical_details") or ""
        chapters["technical_details"] = tech + tech_extra

        datasets_text = chapters.get("datasets") or ""
        chapters["datasets"] = datasets_text + datasets_extra

        experiments = chapters.get("experiments") or ""
        if baselines:
            title = "【VFL Baselines】" if is_vfl else "【联邦 Baselines】"
            experiments += f"\n\n{title}\n" + "\n".join(f"- {b}" for b in baselines[:12])
        metrics = plan.get("metrics") or []
        if metrics:
            experiments += "\n\n【评估指标】\n" + "\n".join(f"- {m}" for m in metrics[:10])
        chapters["experiments"] = experiments

        results = chapters.get("results") or ""
        vfl_tag = "VFL " if is_vfl else ""
        results += (
            f"\n\n【{vfl_tag}Pilot 结果】execution_mode={mode}；来源：{result_source}。"
            f" best_method={federated_pilot.get('best_method', 'N/A')}。"
        )
        if is_vfl:
            results += (
                "\n对齐与隐私：关注 alignment_success_rate、aligned_sample_rate、"
                "privacy_leakage_risk；可根据 pilot 建议调整下一轮 communication_rounds。"
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

        hypothesis = experiment_design.get("hypothesis") or ""
        verifiable = experiment_design.get("verifiable_hypothesis") or build_verifiable_hypothesis_spec(
            hypothesis, plan, fl_context
        )
        actions = federated_pilot.get("replan_actions") or (
            (federated_pilot.get("skill_outputs") or {}).get("federated_replanning") or {}
        ).get("replan_actions") or []
        subsections = build_campaign_lineage_text(
            federated_pilot,
            actions,
            verifiable_spec=verifiable,
            snapshots=iteration_snapshots,
        )
        pareto = federated_pilot.get("pareto_frontier") or compute_pareto_frontier(
            federated_pilot.get("metric_comparison") or []
        )
        if pareto.get("frontier"):
            pf_lines = "\n".join(
                f"- {p.get('method')}: acc={p.get('accuracy')}, comm={p.get('communication_cost')}"
                for p in pareto["frontier"][:5]
            )
            subsections["results"] = append_subsections_to_chapter(
                subsections.get("results", ""),
                f"### 精度—通信 Pareto 前沿\n\n{pf_lines}\n"
                f"推荐权衡点：**{pareto.get('best_tradeoff_method', '—')}**",
            )
        pf3 = federated_pilot.get("pareto_frontier_3d") or compute_pareto_frontier_3d(
            federated_pilot.get("metric_comparison") or []
        )
        if pf3.get("frontier_3d"):
            lines3 = "\n".join(
                f"- {p.get('method')}: acc={p.get('accuracy')}, comm={p.get('communication_cost')}, "
                f"privacy={p.get('privacy_risk')}"
                for p in pf3["frontier_3d"][:5]
            )
            subsections["results"] = append_subsections_to_chapter(
                subsections.get("results", ""),
                f"### 三维 Pareto 前沿（Accuracy / Communication / Privacy）\n\n{lines3}\n"
                f"推荐：**{pf3.get('best_tradeoff_method', '—')}**",
            )
        chapters["methods"] = append_subsections_to_chapter(
            chapters.get("methods") or experiment_design.get("methods"), subsections.get("methods", "")
        )
        chapters["rationale"] = append_subsections_to_chapter(
            chapters.get("rationale"), subsections.get("rationale", "")
        )
        chapters["experiments"] = append_subsections_to_chapter(
            chapters.get("experiments"), subsections.get("experiments", "")
        )
        chapters["results"] = append_subsections_to_chapter(
            chapters.get("results"), subsections.get("results", "")
        )
        return chapters


def get_federated_experiment_service(db=None) -> FederatedExperimentService:
    return FederatedExperimentService(db)
