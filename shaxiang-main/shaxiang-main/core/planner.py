import logging
from typing import Optional

from llm.client import LLMClient
from llm.prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_TEMPLATE,
    SANDBOX_PARAM_ONLY_SYSTEM_PROMPT,
    SANDBOX_PARAM_ONLY_USER_TEMPLATE,
)
from schemas.experiment import Experiment, ExperimentPlan
from schemas.analysis import AnalysisReport, IterationDecision
from storage.repository import Repository

logger = logging.getLogger(__name__)


class ExperimentPlanner:
    """AI 驱动的实验方案规划器"""

    def __init__(self, llm_client: LLMClient, repository: Repository):
        self.llm = llm_client
        self.repository = repository

    def generate_initial_plan(self, research_goal: str, constraints: list[str]) -> ExperimentPlan:
        """生成初始实验方案（第 1 轮）"""
        prompt = PLANNER_USER_TEMPLATE.render(
            research_goal=research_goal,
            constraints=constraints,
            previous_plan=None,
            previous_analysis_summary=None,
            history_summaries=None,
        )
        plan = self.llm.generate_to_model(
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            model_class=ExperimentPlan,
        )
        logger.info(f"生成初始实验方案: {plan.title}")
        return plan

    def generate_adapted_plan(
        self,
        experiment: Experiment,
        previous_analysis: AnalysisReport,
        previous_decision: IterationDecision,
        previous_status: str = "success",
        error_message: str = "",
        column_contract: Optional[dict] = None,
        previous_script: str = "",
        locked_plan: Optional[ExperimentPlan] = None,
        force_script_rewrite: bool = False,
    ) -> ExperimentPlan:
        """
        根据上一轮反馈生成调整后的方案。

        sandbox:
        - success 且无强制重写 → 只调 script_params，硬锁定成功脚本正文
        - failed / force_script_rewrite → 局部修补或更大改动（由 engine 的反馈路径主导全量重设计）
        """
        latest = self.repository.get_latest_iteration(experiment.id)
        prev_plan = None
        if latest and latest.plan:
            try:
                prev_plan = ExperimentPlan.model_validate(latest.plan)
            except Exception:
                prev_plan = None
        if prev_plan is None:
            prev_plan = experiment.initial_plan

        # 成功脚本优先：避免从失败/占位正文继续发散
        base_plan = prev_plan
        if locked_plan is not None:
            if previous_status == "success" and not force_script_rewrite:
                base_plan = locked_plan
            else:
                latest_script = (
                    ((prev_plan.parameters or {}).get("script") if prev_plan else "")
                    or (prev_plan.analysis_script if prev_plan else "")
                    or ""
                ).strip()
                if len(latest_script) < 80 or "see analysis_script" in latest_script.lower():
                    base_plan = locked_plan
                    previous_script = (
                        (locked_plan.parameters or {}).get("script")
                        or locked_plan.analysis_script
                        or previous_script
                    )

        analysis_summary = (
            f"整体评估: {previous_analysis.overall_assessment}\n"
            f"摘要: {previous_analysis.summary}\n"
            f"问题: {'; '.join(previous_analysis.identified_issues)}\n"
            f"建议: {'; '.join(previous_analysis.suggested_adjustments)}"
        )
        feedback = (getattr(experiment, "human_feedback", None) or "").strip()
        if feedback:
            analysis_summary += f"\n人工反馈: {feedback}"

        use_sandbox = getattr(experiment, "executor_type", "") == "sandbox"
        if use_sandbox and base_plan is not None:
            # sandbox 主路径已改由 ScriptDesigner 每轮重设计；此处仅作局部修补兜底
            return self._patch_sandbox_script(
                experiment=experiment,
                prev_plan=base_plan,
                analysis_summary=analysis_summary,
                error_message=error_message or previous_analysis.summary,
                column_contract=column_contract or {},
                previous_script=previous_script,
            )

        # 非 sandbox：沿用旧逻辑
        history = self.repository.get_metrics_history(experiment.id)
        history_summaries = []
        for h in history[:-1]:
            history_summaries.append({
                "iteration": h.get("iteration", "?"),
                "brief_result": ", ".join(
                    f"{k}={v}" for k, v in h.items() if k != "iteration" and isinstance(v, (int, float))
                ),
            })

        prompt = PLANNER_USER_TEMPLATE.render(
            research_goal=experiment.research_goal,
            constraints=experiment.constraints,
            previous_plan=prev_plan,
            previous_analysis_summary=analysis_summary,
            history_summaries=history_summaries if history_summaries else None,
        )
        plan = self.llm.generate_to_model(
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            model_class=ExperimentPlan,
        )
        logger.info(f"生成调整后实验方案 (第{experiment.current_iteration + 1}轮): {plan.title}")
        return plan

    def _adapt_sandbox_params_only(
        self,
        experiment: Experiment,
        prev_plan: ExperimentPlan,
        analysis_summary: str,
        column_contract: dict,
    ) -> ExperimentPlan:
        """成功轮：保留脚本，仅更新 script_params。"""
        current_params = dict(prev_plan.script_params or {})
        params = dict(prev_plan.parameters or {})
        if isinstance(params.get("script_params"), dict):
            current_params.update(params["script_params"])

        prompt = SANDBOX_PARAM_ONLY_USER_TEMPLATE.render(
            research_goal=experiment.research_goal,
            numeric_columns=column_contract.get("numeric_columns", []),
            non_numeric_columns=column_contract.get("non_numeric_columns", []),
            current_script_params=current_params,
            previous_analysis_summary=analysis_summary,
        )
        try:
            raw = self.llm.generate_structured(
                prompt=prompt,
                system_prompt=SANDBOX_PARAM_ONLY_SYSTEM_PROMPT,
                output_schema={
                    "type": "object",
                    "properties": {"script_params": {"type": "object"}},
                    "required": ["script_params"],
                },
                temperature=0.2,
            )
            new_params = raw.get("script_params") or {}
            if not isinstance(new_params, dict):
                new_params = {}
        except Exception as e:
            logger.warning(f"参数调优失败，沿用上轮参数: {e}")
            new_params = {}

        merged = dict(current_params)
        merged.update(new_params)

        # 强制 feature_columns 落在数值列内
        numeric_cols = set(column_contract.get("numeric_columns") or [])
        feats = merged.get("feature_columns")
        if isinstance(feats, list) and numeric_cols:
            merged["feature_columns"] = [c for c in feats if c in numeric_cols] or list(numeric_cols)[:9]

        from core.script_repair import get_plan_script, normalize_column_params

        plan = prev_plan.model_copy(deep=True)
        plan.script_params = merged
        plan_params = dict(plan.parameters or {})
        plan_params["script_params"] = merged
        # 硬锁定脚本正文：绝不用 LLM 输出覆盖
        script = get_plan_script(prev_plan)
        plan_params["script"] = script
        plan.parameters = plan_params
        plan.analysis_script = script
        if column_contract:
            plan = normalize_column_params(plan, column_contract)
        logger.info("sandbox 成功轮：仅调整 script_params，脚本正文已锁定")
        return plan

    def _patch_sandbox_script(
        self,
        experiment: Experiment,
        prev_plan: ExperimentPlan,
        analysis_summary: str,
        error_message: str,
        column_contract: dict,
        previous_script: str = "",
    ) -> ExperimentPlan:
        """失败轮：基于上轮/锁定脚本局部修补（真正的多轮试跑在 engine 修复循环中）。"""
        from core.script_repair import get_plan_script, patch_plan_from_error

        base = prev_plan.model_copy(deep=True)
        if previous_script and len(previous_script.strip()) >= 80:
            params = dict(base.parameters or {})
            params["script"] = previous_script.strip()
            base.parameters = params
            base.analysis_script = previous_script.strip()

        plan = patch_plan_from_error(
            self.llm,
            base,
            research_goal=experiment.research_goal,
            column_contract=column_contract or {},
            error_message=error_message,
            analysis_summary=analysis_summary,
        )
        if len(get_plan_script(plan)) < 80:
            logger.warning("修补脚本无效，回退基线脚本正文")
            plan = base
        logger.info("sandbox 失败轮：已产出局部修补草案（待 smoke 循环验收）")
        return plan

    def compare_plans(self, old_plan: dict, new_plan: dict) -> list[dict]:
        """对比两轮方案差异"""
        changes = []
        all_keys = set(list(old_plan.keys()) + list(new_plan.keys()))
        for key in all_keys:
            old_val = old_plan.get(key)
            new_val = new_plan.get(key)
            if old_val != new_val:
                change_type = "modified"
                if old_val is None:
                    change_type = "added"
                elif new_val is None:
                    change_type = "removed"
                changes.append({
                    "field": key,
                    "old": str(old_val)[:100],
                    "new": str(new_val)[:100],
                    "change_type": change_type,
                })
        return changes
