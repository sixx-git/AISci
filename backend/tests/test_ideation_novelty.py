"""Ideation 新颖性 Skill 单元测试"""
from unittest.mock import AsyncMock, patch

from app.skills.reasoning.ideation_novelty_skill import IdeationNoveltySkill


def test_ideation_novelty_with_mock_search():
    import asyncio

    async def _run():
        skill = IdeationNoveltySkill()
        mock_papers = [
            {"title": "Gut microbiome and Alzheimer disease", "abstract": "gut brain axis", "year": 2023, "source": "openalex"},
            {"title": "Unrelated physics paper", "abstract": "quantum", "year": 2020, "source": "semantic_scholar"},
        ]

        with patch.object(
            IdeationNoveltySkill,
            "_llm_synthesize",
            return_value={
                "novelty_score": 7.2,
                "novelty_risk": "medium",
                "suggested_angles": ["方向A", "方向B", "方向C"],
                "research_gaps": ["gap1"],
                "avoid_topics": ["已饱和"],
                "assessment": "有探索空间",
            },
        ):
            with patch("app.skills.reasoning.ideation_novelty_skill.SearchPapersSkill") as MockSearch:
                instance = MockSearch.return_value
                instance.run = AsyncMock(
                    return_value=type("R", (), {"success": True, "data": {"papers": mock_papers}, "warnings": []})()
                )
                return await skill.run(
                    input_data={
                        "research_question": "肠道菌群如何影响阿尔茨海默病认知功能",
                        "knowledge_gaps": [{"gap": "缺少纵向队列"}],
                        "num_ideas": 3,
                    },
                    context={},
                )

    result = asyncio.run(_run())
    assert result.success
    assert result.data["external_papers_count"] == 2
    assert len(result.data["suggested_angles"]) == 3
    assert result.data["novelty_score"] == 7.2


def test_resolve_run_options_discovery():
    from app.core.pipeline_modes import resolve_run_options, PipelineMode

    opts = resolve_run_options({"pipeline_mode": "discovery", "num_ideas": 5})
    assert opts["pipeline_mode"] == PipelineMode.DISCOVERY.value
    assert opts["num_ideas"] == 5
    assert opts["force_sandbox"] is True
