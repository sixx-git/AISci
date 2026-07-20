"""
分析脚本设计模块

职责：根据用户上传的具体数据 + 实验假设，设计分析脚本和参数。
支持人工反馈驱动的高自由度重设计。
"""
import logging
from typing import Optional

from llm.client import LLMClient
from llm.prompts import SCRIPT_DESIGNER_SYSTEM_PROMPT, SCRIPT_DESIGNER_USER_TEMPLATE
from schemas.experiment import ExperimentPlan
from storage.repository import Repository

logger = logging.getLogger(__name__)


class ScriptDesigner:
    """AI 驱动的分析脚本设计器"""

    def __init__(self, llm_client: LLMClient, repository: Repository):
        self.llm = llm_client
        self.repository = repository

    def design_script(
        self,
        hypothesis: str,
        data_config: dict,
        dataset_metadata: dict = None,
        previous_plan: ExperimentPlan = None,
        previous_analysis_summary: str = None,
        constraints: list[str] = None,
        human_feedback: str = None,
        current_script: str = None,
        allow_full_rewrite: bool = False,
    ) -> ExperimentPlan:
        """
        根据假设和具体数据，设计分析方案（含脚本和参数）。

        human_feedback / allow_full_rewrite:
            允许按人工意见高自由度重写脚本，而不是只调参。
        """
        feedback = (human_feedback or "").strip()
        script_text = (current_script or "").strip()
        if not script_text and previous_plan is not None:
            script_text = (
                (previous_plan.parameters or {}).get("script")
                or previous_plan.analysis_script
                or ""
            ).strip()

        # 有人工反馈时默认进入高自由度重设计
        full_rewrite = bool(allow_full_rewrite or feedback)

        prompt = SCRIPT_DESIGNER_USER_TEMPLATE.render(
            hypothesis=hypothesis,
            dataset_metadata=dataset_metadata or {},
            data_config_summary=_summarize_data_config(data_config),
            previous_plan=previous_plan,
            previous_analysis_summary=previous_analysis_summary,
            constraints=constraints or [],
            human_feedback=feedback or None,
            current_script=script_text[:12000] if script_text else None,
            allow_full_rewrite=full_rewrite,
        )

        plan = self.llm.generate_to_model(
            prompt=prompt,
            system_prompt=SCRIPT_DESIGNER_SYSTEM_PROMPT,
            model_class=ExperimentPlan,
        )

        from core.script_repair import infer_experiment_paradigm, normalize_column_params

        params = dict(plan.parameters or {})
        params["data_config"] = dict(data_config)
        script = (params.get("script") or plan.analysis_script or "").strip()
        params["script"] = script
        script_params = dict(plan.script_params or {})
        if isinstance(params.get("script_params"), dict):
            script_params.update(params["script_params"])

        # 设计完成后写入推断范式，供 smoke 修复分治使用（可被 LLM 显式字段覆盖）
        if not script_params.get("experiment_paradigm") and not script_params.get("_experiment_paradigm"):
            paradigm = infer_experiment_paradigm(
                research_goal=hypothesis or "",
                human_feedback=feedback or "",
                script=script,
            )
            script_params["experiment_paradigm"] = paradigm

        params["script_params"] = script_params
        plan.parameters = params
        plan.script_params = script_params
        plan.analysis_script = plan.analysis_script or script
        plan = normalize_column_params(plan, dataset_metadata or {})

        logger.info(
            "设计分析方案: %s (full_rewrite=%s, feedback=%s, paradigm=%s)",
            plan.title,
            full_rewrite,
            bool(feedback),
            script_params.get("experiment_paradigm"),
        )
        return plan


def _summarize_data_config(data_config: dict) -> str:
    """将 data_config 摘要为可读文本"""
    parts = [f"类型: {data_config.get('source_type', '?')}"]
    if data_config.get('source_path'):
        parts.append(f"路径: {data_config['source_path']}")
    if data_config.get('profile_name'):
        parts.append(f"profile: {data_config['profile_name']}")
    if data_config.get('column_mapping'):
        parts.append(f"列映射: {data_config['column_mapping']}")
    if data_config.get('preprocessing_steps'):
        parts.append(f"预处理: {data_config['preprocessing_steps']}")
    if data_config.get('sample_size'):
        parts.append(f"采样: {data_config['sample_size']}")
    return "; ".join(parts)
