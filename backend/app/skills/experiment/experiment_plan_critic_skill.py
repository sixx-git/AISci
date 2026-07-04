"""
实验计划批评 Skill
参考能力：AI Scientist reflective review
——对实验设计进行 LLM 批判性审查，补充 SanityCheck 的语义层面评估。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult
from app.skills.experiment.experiment_sanity_check_skill import ExperimentSanityCheckSkill

logger = logging.getLogger(__name__)


class ExperimentPlanCriticSkill(BaseSkill):
    """实验计划批评 Skill

    输入:
      - experiment_design: dict
      - hypothesis: str
      - literature_facts: List[dict]
      - data_context: dict

    输出 (SkillResult.data):
      - feasibility_score: float       0-10
      - critical_issues: List[str]
      - warnings: List[str]
      - recommendations: List[str]
      - critic_summary: str
      - sanity_check: dict             ExperimentSanityCheck 结果
      - passed: bool
    """

    name = "ExperimentPlanCritic"
    description = "对实验计划进行批判性审查，评估可行性与设计缺陷"
    source_reference = "AI Scientist (arxiv:2408.06292) — reflective experiment review"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        design = input_data.get("experiment_design") or {}
        if not isinstance(design, dict):
            design = {}
        hypothesis = (input_data.get("hypothesis") or "").strip()
        facts = input_data.get("literature_facts") or []
        data_context = input_data.get("data_context") or {}

        sanity_skill = ExperimentSanityCheckSkill()
        sanity_res = await sanity_skill.run({"experiment_design": design}, context)
        sanity_data = sanity_res.data or {}

        try:
            facts_text = "\n".join(
                f"- {f.get('content', '')[:150]}" for f in facts[:8]
            )
            data_hint = ""
            if data_context.get("merged_csv_path") or data_context.get("datasets"):
                data_hint = "已有项目数据集/合并表可用"
            elif data_context.get("recommended_datasets"):
                data_hint = f"推荐数据集 {len(data_context['recommended_datasets'])} 个"

            prompt = (
                "你是实验设计审查专家。请批判性评估以下实验计划。\n\n"
                f"## 假设\n{hypothesis or '—'}\n\n"
                f"## 实验设计\n"
                f"- methods: {(design.get('methods') or '')[:800]}\n"
                f"- datasets: {(design.get('datasets') or design.get('source_data') or '')[:400]}\n"
                f"- baselines: {(design.get('baselines') or '')[:400]}\n"
                f"- metrics: {(design.get('metrics') or '')[:300]}\n"
                f"- steps: {(design.get('experimental_steps') or '')[:600]}\n\n"
                f"## 文献证据\n{facts_text or '—'}\n\n"
                f"## 数据上下文\n{data_hint or '—'}\n\n"
                f"## 结构检查结果\n"
                f"executable={sanity_data.get('executable')}, "
                f"missing={sanity_data.get('missing_items', [])}\n\n"
                "请输出结构化批评意见。"
            )
            schema = {
                "feasibility_score": 7.0,
                "critical_issues": ["缺少统计检验设计"],
                "warnings": ["baseline 描述较笼统"],
                "recommendations": ["补充具体数据集规模与划分方式"],
                "critic_summary": "整体可行但需完善统计检验",
                "passed": True,
            }
            llm = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema,
                prompt_version="experiment_plan_critic",
            )

            feasibility = float(llm.get("feasibility_score", 7.0))
            passed = bool(llm.get("passed", feasibility >= 6.0)) and bool(sanity_data.get("executable", False))
            critical = list(llm.get("critical_issues") or [])
            warnings = list(llm.get("warnings") or []) + list(sanity_res.warnings or [])
            recommendations = list(llm.get("recommendations") or []) + list(sanity_data.get("recommendations") or [])

            if critical:
                result.add_warning(f"实验计划存在 {len(critical)} 个关键问题")
            if not passed:
                result.add_warning("实验计划审查未通过，建议修订后再执行")

            result.data = {
                "feasibility_score": feasibility,
                "critical_issues": critical,
                "warnings": warnings,
                "recommendations": recommendations,
                "critic_summary": str(llm.get("critic_summary", "")),
                "sanity_check": sanity_data,
                "passed": passed,
            }
            return result

        except Exception as e:
            logger.exception("ExperimentPlanCriticSkill 异常: %s", e)
            result.add_error(f"实验计划批评异常: {e}")
            result.data = {"sanity_check": sanity_data, "passed": False}
            return result
