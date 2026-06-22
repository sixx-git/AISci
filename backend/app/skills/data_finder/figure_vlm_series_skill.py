"""图表 VLM/规则 L2 序列抽取 Skill"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.figure_extraction import extract_rule_series_from_caption
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class FigureVlmSeriesSkill(BaseSkill):
    name = "FigureVlmSeries"
    description = "从论文图表 caption/图像抽取近似数据序列（低置信）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        caption = input_data.get("caption", "") or ""
        series = input_data.get("possible_data_series") or []
        image_path = input_data.get("image_path") or ""
        research_question = input_data.get("research_question", "") or ""

        rows: List[Dict[str, Any]] = []
        method = "rule_series"
        confidence = 0.45

        if image_path:
            try:
                from app.skills.multimodal.qwen_vl_image_understanding_skill import QwenVlImageUnderstandingSkill

                vl_skill = QwenVlImageUnderstandingSkill()
                vl_res = await vl_skill.run(
                    {
                        "image_path": image_path,
                        "research_question": research_question,
                        "context": caption[:500],
                    },
                    context,
                )
                vl_data = vl_res.data or {}
                trends = vl_data.get("key_trends") or []
                elements = vl_data.get("detected_elements") or []
                if trends or elements:
                    method = "vlm"
                    confidence = 0.55
                    for i, t in enumerate((trends or elements)[:6]):
                        rows.append({
                            "series": str(t)[:80],
                            "value": "",
                            "unit": "vlm_trend",
                            "_provenance_extraction_method": "vlm",
                            "_confidence": confidence,
                        })
            except Exception as exc:
                logger.warning("Figure VLM 抽取失败，降级规则: %s", exc)
                result.add_warning(f"VLM 降级: {exc}")

        if not rows:
            rows = extract_rule_series_from_caption(caption, series)

        result.data = {
            "rows": rows,
            "extraction_method": method,
            "extraction_confidence": confidence,
            "needs_manual_review": confidence < 0.65,
        }
        return result
