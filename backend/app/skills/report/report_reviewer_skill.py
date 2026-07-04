"""
报告审查 Skill
参考能力：AI Scientist reviewer、挑战杯赛题规范
——对完整报告进行 holistic 审查，补充 ReportQualityCheck 的语义评估。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult
from app.skills.report.report_quality_check_skill import ReportQualityCheckSkill

logger = logging.getLogger(__name__)

REPORT_SECTION_KEYS = [
    "paper_title", "paper_abstract", "problem_statement", "rationale",
    "technical_details", "datasets", "methods", "experiments", "results", "references",
]


class ReportReviewerSkill(BaseSkill):
    """报告审查 Skill

    输入:
      - report_data: dict
      - citation_grounding: dict
      - compliance_metrics: dict
      - pipeline_context: dict

    输出 (SkillResult.data):
      - review_score: float            0-10
      - publish_ready: bool
      - strengths: List[str]
      - weaknesses: List[str]
      - revision_priorities: List[str]
      - reviewer_summary: str
      - quality_check: dict
    """

    name = "ReportReviewer"
    description = "对科研报告进行整体性审查，输出修订优先级与发布就绪判断"
    source_reference = "AI Scientist — automated reviewer; 挑战杯 XH-202619 赛题规范"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        report_data = input_data.get("report_data") or {}
        citation_grounding = input_data.get("citation_grounding") or {}
        compliance = input_data.get("compliance_metrics") or {}
        pipeline_context = input_data.get("pipeline_context") or {}

        qc_skill = ReportQualityCheckSkill()
        qc_res = await qc_skill.run(
            {
                "report_data": report_data,
                "references_verified": compliance.get("references_verified", 0),
                "citation_grounding_output": citation_grounding,
                "has_real_data_plots": compliance.get("has_real_data_plots", False),
            },
            context,
        )
        qc_data = qc_res.data or {}

        try:
            sections_preview = self._preview_sections(report_data)
            risk = citation_grounding.get("risk_level", "unknown")
            ref_verified = compliance.get("references_verified", 0)

            prompt = (
                "你是科研报告审稿人。请对以下报告进行 holistic 审查。\n\n"
                f"## 报告摘要\n{sections_preview}\n\n"
                f"## 引用风险\nrisk_level={risk}, verified_refs={ref_verified}\n\n"
                f"## 合规检查\nscore={qc_data.get('score')}, "
                f"critical={qc_data.get('critical_issues', [])[:3]}\n\n"
                f"## Pipeline 上下文\n"
                f"has_experiment_design={bool(pipeline_context.get('experiment_design'))}\n"
                f"has_validation={bool(pipeline_context.get('small_validation'))}\n\n"
                "评估: 逻辑连贯性、证据充分性、实验可复现性、引用规范性。"
            )
            schema = {
                "review_score": 7.5,
                "publish_ready": False,
                "strengths": ["问题陈述清晰"],
                "weaknesses": ["实验细节不足"],
                "revision_priorities": ["补充 baseline 对比"],
                "reviewer_summary": "整体合格，需修订实验章节",
            }
            llm = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema,
                prompt_version="report_reviewer",
            )

            review_score = float(llm.get("review_score", qc_data.get("score", 0) / 10.0))
            publish_ready = bool(llm.get("publish_ready", False))
            if qc_data.get("critical_issues"):
                publish_ready = False

            weaknesses = list(llm.get("weaknesses") or [])
            if qc_data.get("critical_issues"):
                weaknesses = list(dict.fromkeys(weaknesses + qc_data["critical_issues"][:3]))

            if not publish_ready:
                result.add_warning("报告尚未达到发布就绪标准")

            result.data = {
                "review_score": review_score,
                "publish_ready": publish_ready,
                "strengths": list(llm.get("strengths") or []),
                "weaknesses": weaknesses,
                "revision_priorities": list(llm.get("revision_priorities") or []),
                "reviewer_summary": str(llm.get("reviewer_summary", "")),
                "quality_check": qc_data,
            }
            result.warnings.extend(qc_res.warnings)
            return result

        except Exception as e:
            logger.exception("ReportReviewerSkill 异常: %s", e)
            result.add_error(f"报告审查异常: {e}")
            result.data = {"quality_check": qc_data, "publish_ready": False, "review_score": 0.0}
            return result

    @staticmethod
    def _preview_sections(report_data: dict) -> str:
        lines: List[str] = []
        for key in REPORT_SECTION_KEYS:
            val = report_data.get(key) or ""
            if isinstance(val, dict):
                val = str(val)[:200]
            else:
                val = str(val)[:200]
            if val.strip():
                lines.append(f"### {key}\n{val}")
        return "\n\n".join(lines[:8]) or "（报告内容为空）"
