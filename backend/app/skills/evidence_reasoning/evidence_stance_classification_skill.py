"""证据立场分类 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.evidence_reasoning._utils import COUNTER_KEYWORDS, normalize_text


class EvidenceStanceClassificationSkill(BaseSkill):
    name = "EvidenceStanceClassification"
    description = "判断证据对假设的支持/反对/中性立场"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        hypothesis = normalize_text(input_data.get("hypothesis", ""))
        evidence_list: List[Dict[str, Any]] = input_data.get("evidence_list", [])

        classified: List[Dict[str, Any]] = []
        for ev in evidence_list:
            item = dict(ev)
            preset = item.get("stance")
            text = normalize_text(f"{item.get('claim', '')} {item.get('quote_or_summary', '')}")

            if preset in {"support", "refute", "neutral"}:
                stance = preset
                reason = f"检索阶段已标记为 {stance}"
            elif any(kw in text for kw in COUNTER_KEYWORDS):
                stance = "refute"
                reason = "文本包含限制/失败/风险等反对性关键词"
            elif hypothesis and any(t in text for t in hypothesis.split()[:6] if len(t) >= 3):
                stance = "support"
                reason = "证据内容与假设核心术语一致"
            else:
                stance = "neutral"
                reason = "与假设关联较弱，暂作中性证据"

            item["stance"] = stance
            item["stance_reason"] = reason
            classified.append(item)

        result.data = {"classified_evidence": classified}
        return result
