"""导师评审 Skill — 对假设/实验设计/报告给出结构化修改建议"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.services.qwen_client import qwen_structured_chat
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

MENTOR_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "revision_suggestions": {"type": "array", "items": {"type": "string"}},
        "risk_points": {"type": "array", "items": {"type": "string"}},
        "required_additional_evidence": {"type": "array", "items": {"type": "string"}},
        "overall_assessment": {"type": "string"},
        "readiness_score": {"type": "integer"},
    },
    "required": [
        "strengths",
        "weaknesses",
        "revision_suggestions",
        "risk_points",
        "required_additional_evidence",
    ],
}


class MentorReviewSkill(BaseSkill):
    name = "MentorReview"
    description = "模拟导师对科研阶段产出进行结构化评审"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        target_type = input_data.get("target_type", "hypothesis")
        content = input_data.get("content") or {}
        research_question = input_data.get("research_question", "")
        user_notes = input_data.get("user_notes", "")

        prompt = self._build_prompt(target_type, content, research_question, user_notes)
        try:
            raw = qwen_structured_chat(
                messages=[{"role": "user", "content": prompt}],
                response_schema=MENTOR_REVIEW_SCHEMA,
                prompt_version="mentor_review",
                temperature=0.3,
            )
            review = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            logger.warning(f"MentorReview LLM 失败，使用规则降级: {exc}")
            review = self._fallback_review(target_type, content)

        result.data = {
            "target_type": target_type,
            "review": review,
        }
        return result

    @staticmethod
    def _build_prompt(
        target_type: str,
        content: Dict[str, Any],
        research_question: str,
        user_notes: str,
    ) -> str:
        content_text = json.dumps(content, ensure_ascii=False, indent=2)[:12000]
        return f"""你是一位严谨的研究生导师，正在评审学生的科研{target_type}产出。

研究问题：{research_question}
用户补充说明：{user_notes or '无'}

待评审内容（JSON）：
{content_text}

请从以下维度给出结构化评审（中文）：
1. strengths — 优点与亮点（3-5条）
2. weaknesses — 不足与漏洞（3-5条）
3. revision_suggestions — 具体可执行的修改建议（3-6条）
4. risk_points — 科研/方法/伦理风险（2-4条）
5. required_additional_evidence — 还需补充的证据或实验（2-4条）
6. overall_assessment — 一段总体评价
7. readiness_score — 0-100，表示进入下一阶段的就绪度

要求：建议必须具体、可执行，避免空泛套话。"""

    @staticmethod
    def _fallback_review(target_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
        has_content = bool(content)
        return {
            "strengths": ["结构完整，包含关键科研要素"] if has_content else [],
            "weaknesses": ["需补充更多可验证细节"] if has_content else ["内容为空或过少"],
            "revision_suggestions": [
                "明确可测量指标与对照基线",
                "补充数据来源与引用依据",
                "细化实验步骤与预期结果",
            ],
            "risk_points": ["假设可能缺乏充分文献支撑", "实验设计可能存在 confounders"],
            "required_additional_evidence": ["补充关键文献引用", "增加小样验证数据"],
            "overall_assessment": f"{target_type} 产出需要进一步人工完善后再进入下一阶段。",
            "readiness_score": 55 if has_content else 20,
        }
