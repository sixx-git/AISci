"""图像/图表元信息抽取 Skill"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult


CHART_TYPE_HINTS = {
    "bar": ["bar chart", "柱状", "bar plot"],
    "line": ["line chart", "折线", "curve", "convergence"],
    "scatter": ["scatter", "散点"],
    "heatmap": ["heatmap", "热图"],
    "box": ["box plot", "箱线"],
}


class FigureDataExtractionSkill(BaseSkill):
    name = "FigureDataExtraction"
    description = "抽取论文图表元信息，低置信度不写入正式 CSV"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        figures_detected = input_data.get("figures_detected", []) or []
        paper_id = input_data.get("paper_id", "")
        source_title = input_data.get("source_title", "")
        raw_text = input_data.get("raw_text", "") or ""

        figures_out: List[Dict[str, Any]] = []
        for fig in figures_detected:
            caption = fig.get("caption", "") or ""
            fig_num = fig.get("figure_number", "")
            caption_l = caption.lower()

            chart_type = "unknown"
            for ctype, hints in CHART_TYPE_HINTS.items():
                if any(h in caption_l for h in hints):
                    chart_type = ctype
                    break

            axis_labels = self._guess_axis_labels(caption, raw_text, fig_num)
            legend = self._guess_legend(caption)
            series = self._guess_series(caption, legend)

            confidence = 0.35
            if chart_type != "unknown":
                confidence += 0.2
            if axis_labels.get("x") or axis_labels.get("y"):
                confidence += 0.15
            if series:
                confidence += 0.1
            confidence = round(min(1.0, confidence), 4)

            figures_out.append({
                "figure_id": f"fig_{paper_id}_{fig_num}",
                "paper_id": paper_id,
                "source_title": source_title,
                "figure_number": fig_num,
                "caption": caption,
                "chart_type": chart_type,
                "axis_labels": axis_labels,
                "legend": legend,
                "possible_data_series": series,
                "extraction_confidence": confidence,
                "extraction_method": "rule",
                "needs_manual_review": confidence < 0.65,
                "included_in_csv": False,
                "review_status": "pending",
            })

        result.data = {"figures": figures_out, "count": len(figures_out)}
        return result

    @staticmethod
    def _guess_axis_labels(caption: str, text: str, fig_num: str) -> Dict[str, str]:
        labels = {"x": "", "y": ""}
        m = re.search(r"(?:x[- ]?axis|横轴)[:\s]+([^,;]+)", caption, re.I)
        if m:
            labels["x"] = m.group(1).strip()
        m = re.search(r"(?:y[- ]?axis|纵轴)[:\s]+([^,;]+)", caption, re.I)
        if m:
            labels["y"] = m.group(1).strip()
        if not labels["x"] and fig_num:
            ctx = re.search(rf"Figure\s*{fig_num}.*?([A-Za-z ]+)\s+vs\.?\s+([A-Za-z ]+)", text[:5000], re.I | re.S)
            if ctx:
                labels["x"] = ctx.group(1).strip()
                labels["y"] = ctx.group(2).strip()
        return labels

    @staticmethod
    def _guess_legend(caption: str) -> List[str]:
        if " vs " in caption.lower():
            parts = re.split(r"\s+vs\.?\s+", caption, flags=re.I)
            return [p.strip() for p in parts if p.strip()][:5]
        return []

    @staticmethod
    def _guess_series(caption: str, legend: List[str]) -> List[str]:
        methods = re.findall(r"(FedAvg|FedProx|SCAFFOLD|LocalOnly|Centralized|[A-Z][a-z]+Net)", caption)
        return list(dict.fromkeys(methods + legend))[:8]
