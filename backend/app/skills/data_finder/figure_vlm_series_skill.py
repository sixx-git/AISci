"""图表 VLM/规则 L2-L4 序列抽取 Skill"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings
from app.core.figure_extraction import extract_rule_series_from_caption
from app.core.figure_digitization import (
    FIGURE_SERIES_SCHEMA_V2,
    infer_tier_from_digitization,
    sanitize_vlm_series_payload,
    series_json_to_rows,
    validate_digitized_series,
)
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()


class FigureVlmSeriesSkill(BaseSkill):
    name = "FigureVlmSeries"
    description = "从论文图表 caption/图像抽取结构化数据序列（L2-L4 分级）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        caption = input_data.get("caption", "") or ""
        series = input_data.get("possible_data_series") or []
        image_path = input_data.get("image_path") or ""
        research_question = input_data.get("research_question", "") or ""
        chart_type = input_data.get("chart_type", "unknown") or "unknown"
        axis_labels = input_data.get("axis_labels") or {}

        rows: List[Dict[str, Any]] = []
        method = "rule_series"
        confidence = 0.45
        checks: List[str] = []
        points_count = 0
        tier = "L2_rule_series"

        if image_path and Path(image_path).exists():
            digitized = await self._try_vlm_digitize(
                image_path, caption, research_question, chart_type, axis_labels,
            )
            if digitized:
                rows = digitized["rows"]
                method = digitized["method"]
                confidence = digitized["confidence"]
                checks = digitized["checks"]
                points_count = digitized["points_count"]
                tier = digitized["tier"]
                if digitized.get("warnings"):
                    for w in digitized["warnings"][:3]:
                        result.add_warning(str(w))

        if not rows:
            rows = extract_rule_series_from_caption(caption, series)
            method = "rule_series"
            confidence = 0.45
            tier = "L2_rule_series"
            points_count = len(rows)

        result.data = {
            "rows": rows,
            "extraction_method": method,
            "extraction_tier": tier,
            "extraction_confidence": confidence,
            "digitization_checks": checks,
            "points_count": points_count,
            "schema_version": "figure_series_v2" if points_count >= 4 and "x" in (rows[0] or {}) else "figure_series_v1",
            "needs_manual_review": confidence < 0.65 or tier != "L4_digitize",
        }
        return result

    async def _try_vlm_digitize(
        self,
        image_path: str,
        caption: str,
        research_question: str,
        chart_type: str,
        axis_labels: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        if not settings.QWEN_API_KEY or settings.USE_MOCK_LLM:
            return None

        ext = Path(image_path).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tiff"}:
            return None

        try:
            image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        except Exception as exc:
            logger.warning("读取图块失败: %s", exc)
            return None

        x_label = axis_labels.get("x") or ""
        y_label = axis_labels.get("y") or ""
        prompt = f"""你是科研图表数字化助手。从图像中提取可复现的数值点列，服务研究问题：
{research_question[:400]}

图注: {caption[:400]}
图表类型: {chart_type}
X轴: {x_label or '未知'} · Y轴: {y_label or '未知'}

要求：
1. 只输出 JSON，字段 series[]（name + points[] 含 x/y 数值）、x_axis_label、y_axis_label、chart_type、warnings[]
2. 折线/散点：尽量给出 ≥10 个 (x,y) 点；柱状图：每个柱一个点
3. 读不出的点不要编造；无法数字化时在 warnings 说明
4. x 尽量单调递增；y 为图中可读数值（非像素坐标）"""

        try:
            from app.services.qwen_client import qwen_vision_structured_chat

            raw = qwen_vision_structured_chat(
                prompt=prompt,
                image_base64=image_b64,
                schema_example=FIGURE_SERIES_SCHEMA_V2,
                prompt_version="figure_series_digitize_v2",
            )
        except Exception as exc:
            logger.warning("VLM 数字化失败: %s", exc)
            return await self._legacy_vlm_fallback(image_path, caption, research_question)

        payload = sanitize_vlm_series_payload(raw if isinstance(raw, dict) else {})
        checks, confidence, points_count = validate_digitized_series(payload)
        rows = series_json_to_rows(payload, base_confidence=confidence)

        if rows:
            method = "vlm_digitize"
            tier = infer_tier_from_digitization(
                method=method,
                confidence=confidence,
                points_count=points_count,
                checks=checks,
            )
            return {
                "rows": rows,
                "method": method,
                "confidence": confidence,
                "checks": checks,
                "points_count": points_count,
                "tier": tier,
                "warnings": payload.get("warnings") or [],
            }

        return await self._legacy_vlm_fallback(image_path, caption, research_question)

    @staticmethod
    async def _legacy_vlm_fallback(
        image_path: str,
        caption: str,
        research_question: str,
    ) -> Dict[str, Any] | None:
        """旧版 Qwen-VL 趋势摘要 → L3（非点列）。"""
        try:
            from app.skills.multimodal.qwen_vl_image_understanding_skill import QwenVlImageUnderstandingSkill

            vl_skill = QwenVlImageUnderstandingSkill()
            vl_res = await vl_skill.run(
                {
                    "image_path": image_path,
                    "research_question": research_question,
                    "context": caption[:500],
                },
                {},
            )
            vl_data = vl_res.data or {}
            trends = vl_data.get("key_trends") or vl_data.get("detected_elements") or []
            if not trends:
                return None
            rows = [
                {
                    "series": str(t)[:80],
                    "value": "",
                    "unit": "vlm_trend",
                    "_provenance_extraction_method": "vlm_structured",
                    "_confidence": 0.55,
                }
                for t in trends[:6]
            ]
            return {
                "rows": rows,
                "method": "vlm_structured",
                "confidence": 0.55,
                "checks": ["vlm_trend_only"],
                "points_count": 0,
                "tier": "L3_vlm",
                "warnings": vl_data.get("warnings") or [],
            }
        except Exception as exc:
            logger.warning("VLM 降级失败: %s", exc)
            return None
