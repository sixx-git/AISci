"""
VLM 图表质量评审 Skill（对齐 AI Scientist v2 plot critique）
——对 matplotlib 图评估清晰度、轴标签、是否误导。
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
settings = get_settings()


class PlotVlmCritiqueSkill(BaseSkill):
    name = "PlotVlmCritique"
    description = "VLM/规则混合评审 matplotlib 图表质量"
    source_reference = "AI Scientist v2 — automated plot quality review"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        plots: List[dict] = input_data.get("plots") or []
        hypothesis = input_data.get("hypothesis") or ""
        critiques: List[dict] = []

        for plot in plots:
            critique = await self._critique_one(plot, hypothesis)
            critiques.append(critique)

        scores = [c.get("overall_score", 5.0) for c in critiques if c.get("overall_score") is not None]
        avg = round(sum(scores) / len(scores), 2) if scores else None
        needs_human = any(c.get("needs_human_review") for c in critiques)
        needs_redraw = any(c.get("needs_redraw") for c in critiques)

        result.data = {
            "critiques": critiques,
            "average_score": avg,
            "plot_count": len(plots),
            "needs_human_review": needs_human,
            "needs_redraw": needs_redraw,
            "pass_threshold": float(input_data.get("pass_threshold", 6.5)),
            "review_mode": self._resolve_review_mode(critiques),
            "degradation_reason": self._degradation_reason(critiques),
        }
        if needs_redraw:
            result.add_warning("部分图表质量未达标，建议重绘或人工复核")
        return result

    async def _critique_one(self, plot: dict, hypothesis: str) -> dict:
        plot_id = plot.get("plot_id") or plot.get("title") or "plot"
        image_path = plot.get("path") or plot.get("file_path")
        image_b64 = plot.get("base64")

        if image_path and os.path.exists(image_path) and not image_b64:
            try:
                image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            except Exception:
                pass

        vlm_result = None
        if image_b64 and settings.QWEN_API_KEY and not settings.USE_MOCK_LLM:
            vlm_result = self._vlm_critique(image_b64, plot, hypothesis)

        if vlm_result:
            return {
                "plot_id": plot_id,
                "overall_score": vlm_result.get("overall_score", 5.0),
                "clarity_score": vlm_result.get("clarity_score"),
                "axis_label_score": vlm_result.get("axis_label_score"),
                "misleading_risk": vlm_result.get("misleading_risk", "medium"),
                "issues": vlm_result.get("issues", []),
                "suggestions": vlm_result.get("suggestions", []),
                "reviewer": "vlm",
                "needs_redraw": float(vlm_result.get("overall_score", 5)) < 6.5,
                "needs_human_review": vlm_result.get("misleading_risk") == "high",
            }

        return self._rule_critique(plot, plot_id)

    @staticmethod
    def _vlm_critique(image_b64: str, plot: dict, hypothesis: str) -> Optional[dict]:
        from app.services.qwen_client import qwen_vision_structured_chat

        title = plot.get("title") or plot.get("plot_id") or "chart"
        prompt = f"""你是科学图表审稿人。评估此 matplotlib 图的质量（与假设：{hypothesis[:120]}）。

关注：清晰度、轴标签是否完整、刻度是否合理、是否可能误导读者、配色/图例。
输出 JSON：overall_score/clarity_score/axis_label_score(0-10)、misleading_risk(low/medium/high)、issues[]、suggestions[]。"""

        schema = {
            "overall_score": 7.0,
            "clarity_score": 7.0,
            "axis_label_score": 7.0,
            "misleading_risk": "low",
            "issues": [],
            "suggestions": [],
        }
        try:
            return qwen_vision_structured_chat(
                prompt=prompt,
                image_base64=image_b64,
                schema_example=schema,
                prompt_version="plot_vlm_critique",
            )
        except Exception as exc:
            logger.warning(f"VLM 图表评审失败 ({title}): {exc}")
            return None

    @staticmethod
    def _rule_critique(plot: dict, plot_id: str) -> dict:
        title = (plot.get("title") or "").strip()
        has_path = bool(plot.get("path") or plot.get("file_path"))
        has_b64 = bool(plot.get("base64"))
        has_axes = bool(plot.get("x_label") or plot.get("y_label") or plot.get("axis_labels"))
        has_legend = plot.get("has_legend") is True or bool(plot.get("legend"))
        score = 6.5
        issues: List[str] = []
        if not settings.QWEN_API_KEY or settings.USE_MOCK_LLM:
            issues.append("未配置 VLM API Key，使用规则降级评审（精度低于真实 VLM）")
            score -= 0.3
        if not title or title == plot_id:
            score -= 1.0
            issues.append("缺少描述性标题")
        if not has_path and not has_b64:
            score -= 2.0
            issues.append("缺少可渲染图像")
        if plot.get("is_generated_from_real_data") is False:
            score -= 0.5
            issues.append("非真实数据生成")
        if not has_axes:
            score -= 0.8
            issues.append("缺少轴标签元数据")
        if not has_legend and plot.get("plot_type") in ("line", "bar", "scatter", "grouped_bar"):
            score -= 0.4
            issues.append("建议补充图例")
        score = round(max(1.0, min(10.0, score)), 2)
        suggestions = ["补充轴标签与图例", "使用更具描述性的标题", "配置 QWEN_API_KEY 启用 VLM 评审"]
        if score >= 6.5:
            suggestions = ["可启用 VLM 评审以获得更精确图表诊断"]
        return {
            "plot_id": plot_id,
            "overall_score": score,
            "clarity_score": score,
            "axis_label_score": score - (0.8 if not has_axes else 0),
            "misleading_risk": "medium" if score < 6.5 else "low",
            "issues": issues,
            "suggestions": suggestions if score < 6.5 else suggestions[:1],
            "reviewer": "rule_fallback",
            "needs_redraw": score < 6.5,
            "needs_human_review": score < 5.0,
            "degradation_reason": "vlm_unavailable" if (not settings.QWEN_API_KEY or settings.USE_MOCK_LLM) else "rule_only",
        }

    @staticmethod
    def _resolve_review_mode(critiques: List[dict]) -> str:
        reviewers = {c.get("reviewer") for c in critiques}
        if reviewers == {"vlm"}:
            return "vlm"
        if "vlm" in reviewers:
            return "mixed"
        return "rule_fallback"

    @staticmethod
    def _degradation_reason(critiques: List[dict]) -> Optional[str]:
        if not critiques:
            return None
        if all(c.get("reviewer") == "rule_fallback" for c in critiques):
            if not settings.QWEN_API_KEY:
                return "未配置 QWEN_API_KEY，图表评审已降级为规则模式"
            if settings.USE_MOCK_LLM:
                return "Mock LLM 模式，图表 VLM 评审已降级为规则模式"
            return "VLM 调用失败，已降级为规则评审"
        return None
