"""新增 Skill 单元测试"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services.skill_registry_service import discover_skills
from app.skills.evidence_reasoning.evidence_grounding_skill import EvidenceGroundingSkill
from app.skills.literature.paper_full_text_rag_skill import PaperFullTextRAGSkill
from app.skills.reasoning.hypothesis_tournament_skill import HypothesisTournamentSkill


NEW_SKILL_IDS = {
    "SearchPapers",
    "PaperFullTextRAG",
    "EvidenceGrounding",
    "HypothesisTournament",
    "ExperimentPlanCritic",
    "ResultVerification",
    "ReportReviewer",
    "CitationIntegrityCheck",
}


def test_new_skills_registered():
    skills = discover_skills(refresh=True)
    by_id = {s.id: s for s in skills}
    missing = [sid for sid in NEW_SKILL_IDS if sid not in by_id]
    assert not missing, f"未注册 Skill: {missing}"


def test_evidence_grounding_filters_ungrounded():
    skill = EvidenceGroundingSkill()
    result = asyncio.run(skill.run(
        {
            "hypothesis": "测试假设",
            "evidence_list": [
                {
                    "claim": "有 chunk 绑定",
                    "source_chunk_id": "c1",
                    "document_id": "d1",
                    "source_title": "Real Paper Title Here",
                    "quote_or_summary": "quote",
                },
                {"claim": "无来源", "source_title": ""},
            ],
            "facts": [{"source_paper_title": "Real Paper Title Here"}],
            "rag_passages": [{"chunk_id": "c1"}],
        },
        {},
    ))
    assert result.success
    assert result.data["grounded_count"] >= 1
    assert result.data["ungrounded_count"] >= 1


def test_paper_full_text_rag_requires_project():
    skill = PaperFullTextRAGSkill()
    result = asyncio.run(skill.run({"research_question": "federated learning"}, {}))
    assert not result.success
    assert any("project_id" in e for e in result.errors)


def test_hypothesis_tournament_single_skips():
    skill = HypothesisTournamentSkill()
    result = asyncio.run(skill.run(
        {"hypotheses": [{"hypothesis": "only one"}]},
        {},
    ))
    assert result.success
    assert result.data["winner_index"] == 0


def test_hypothesis_tournament_pairwise():
    skill = HypothesisTournamentSkill()
    with patch("app.skills.reasoning.hypothesis_tournament_skill.qwen_structured_chat") as mock_qwen:
        mock_qwen.side_effect = [
            {"winner_index": 0, "margin": 0.7, "reason": "A better", "scores": {"A": 8, "B": 5}},
            {"selection_rationale": "A 更可验证"},
        ]
        result = asyncio.run(skill.run(
            {
                "hypotheses": [
                    {"hypothesis": "假设 A", "rationale": "rA"},
                    {"hypothesis": "假设 B", "rationale": "rB"},
                ],
                "research_question": "研究问题",
            },
            {},
        ))
    assert result.success
    assert result.data["winner_index"] in (0, 1)
    assert result.data["ranked_hypotheses"]
