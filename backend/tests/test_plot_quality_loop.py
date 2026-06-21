"""图表质量环单元测试"""
import asyncio

from app.skills.report.plot_vlm_critique_skill import PlotVlmCritiqueSkill


def test_rule_critique_low_score_without_image():
    async def _run():
        skill = PlotVlmCritiqueSkill()
        return await skill.run(
            input_data={
                "plots": [{"plot_id": "fig1", "title": "fig1"}],
                "hypothesis": "测试假设",
            },
            context={},
        )

    result = asyncio.run(_run())
    data = result.data
    assert data["plot_count"] == 1
    assert data["critiques"][0]["reviewer"] == "rule_fallback"
    assert data.get("degradation_reason") or data["critiques"][0].get("degradation_reason")
    assert data["needs_redraw"] or data["needs_human_review"] or (data["average_score"] or 0) < 7
