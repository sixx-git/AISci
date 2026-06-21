"""图表质量闭环 — VLM critique + 低分重绘 / human_review 标记"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core.pipeline_modes import PLOT_CRITIQUE_PASS_SCORE
from app.skills.report.plot_vlm_critique_skill import PlotVlmCritiqueSkill
from app.skills.report.scientific_plot_skill import ScientificPlotSkill

logger = logging.getLogger(__name__)


class PlotQualityLoopService:
    async def run_quality_loop(
        self,
        plots: List[dict],
        *,
        hypothesis: str = "",
        output_dir: str = "",
        data_rows: Optional[List[dict]] = None,
        pass_threshold: float = PLOT_CRITIQUE_PASS_SCORE,
        max_redraw: int = 1,
    ) -> Dict[str, Any]:
        if not plots:
            return {"plots": [], "critique": {}, "redraw_count": 0}

        critique_skill = PlotVlmCritiqueSkill()
        critique_res = await critique_skill.run(
            input_data={"plots": plots, "hypothesis": hypothesis, "pass_threshold": pass_threshold},
            context={"stage": "plot_quality_loop"},
        )
        critique_data = critique_res.data or {}
        working = list(plots)
        redraw_count = 0

        if critique_data.get("needs_redraw") and data_rows and output_dir and max_redraw > 0:
            low_ids = {
                c.get("plot_id")
                for c in (critique_data.get("critiques") or [])
                if c.get("needs_redraw")
            }
            regen_specs = []
            for p in working:
                pid = p.get("plot_id") or p.get("title")
                if pid in low_ids:
                    spec = dict(p)
                    spec["title"] = (p.get("title") or pid) + " (revised)"
                    suggestions = next(
                        (c.get("suggestions") or [] for c in critique_data.get("critiques", []) if c.get("plot_id") == pid),
                        [],
                    )
                    if suggestions:
                        spec["description"] = "; ".join(suggestions[:2])
                    regen_specs.append(spec)

            if regen_specs:
                plot_skill = ScientificPlotSkill()
                regen = await plot_skill.run(
                    input_data={
                        "plot_specs": regen_specs,
                        "data": data_rows,
                        "output_dir": output_dir,
                        "format": "both",
                        "dpi": 150,
                    },
                    context={"stage": "plot_redraw"},
                )
                new_charts = (regen.data or {}).get("charts") or []
                if new_charts:
                    kept = [p for p in working if (p.get("plot_id") or p.get("title")) not in low_ids]
                    working = kept + new_charts
                    redraw_count = 1
                    critique_res = await critique_skill.run(
                        input_data={"plots": working, "hypothesis": hypothesis, "pass_threshold": pass_threshold},
                        context={"stage": "plot_quality_loop_retry"},
                    )
                    critique_data = critique_res.data or critique_data

        return {
            "plots": working,
            "critique": critique_data,
            "critique_warnings": critique_res.warnings,
            "redraw_count": redraw_count,
            "needs_human_review": bool(critique_data.get("needs_human_review")),
        }

    def run_quality_loop_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_quality_loop(**kwargs))


def get_plot_quality_loop_service() -> PlotQualityLoopService:
    return PlotQualityLoopService()
