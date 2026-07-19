"""literature_mining → knowledge_gap → hypothesis_generation 冒烟（mock 下游）。"""
from unittest.mock import MagicMock, patch

from app.services.literature_bundle_service import enrich_literature_mining


def test_gated_literature_bundle_feeds_gap_and_hypothesis_contract():
    """门控后的 literature_mining 仍含下游所需键，且低分摘要不进 facts。"""
    lm = {
        "facts": [
            {
                "fact_id": "fact_001",
                "content": "Federated learning can train fall detectors without sharing raw data.",
                "source_chunk_id": "chunk-1",
                "source_paper_title": "FL for Fall Detection",
                "relevance_score": 0.9,
            }
        ],
        "uncertain_points": ["synthetic data domain gap"],
        "citation_map": [
            {
                "title": "FL for Fall Detection",
                "paper_title": "FL for Fall Detection",
                "document_id": "doc-1",
            }
        ],
        "retrieved_papers": [
            {
                "title": "Cooking bread recipes",
                "abstract": "How to bake sourdough bread at home.",
                "relevance_score": 1,
                "gate_passed": False,
            },
            {
                "title": "FL for Fall Detection",
                "abstract": "Federated learning improves elderly fall detection with synthetic data.",
                "relevance_score": 8,
                "gate_passed": True,
            },
        ],
        "source_papers": ["FL for Fall Detection"],
    }

    with patch("app.core.config.get_settings") as mock_gs:
        mock_gs.return_value = MagicMock(
            LIT_RELEVANCE_GATE_ENABLED=True,
            LIT_PAPER_SCORE_CUTOFF=6,
        )
        enriched = enrich_literature_mining(lm)

    assert enriched["facts"]
    # 低分/未通过门控的摘要不得进 facts
    titles = {(f.get("source_paper_title") or "") for f in enriched["facts"]}
    assert "Cooking bread recipes" not in titles
    assert "uncertain_points" in lm
    assert enriched["citation_map"]
    assert enriched["verified_references_count"] >= 1

    # 下游契约：knowledge_gap / hypothesis 只消费这些键
    gap_input = {
        "research_question": "联邦学习合成数据跌倒检测挑战？",
        "literature_facts": enriched["facts"],
        "uncertain_points": lm["uncertain_points"],
        "citation_map": enriched["citation_map"],
    }
    hypo_input = {
        "research_question": gap_input["research_question"],
        "knowledge_gaps": [{"gap": "域偏移未量化", "related_facts": ["fact_001"]}],
        "literature_facts": enriched["facts"],
    }
    assert gap_input["literature_facts"]
    assert hypo_input["knowledge_gaps"]


def test_pipeline_stage_chain_with_mocked_agents():
    """模拟三阶段串联：mine → gap.analyze → hypo.generate，输出键稳定。"""
    lit_resp = MagicMock()
    lit_resp.model_dump.return_value = {
        "facts": [{"fact_id": "f1", "content": "fact", "source_chunk_id": "c1"}],
        "uncertain_points": ["u1"],
        "citation_map": [{"title": "P1", "paper_title": "P1"}],
        "retrieved_papers": [],
        "skill_outputs": {"chunk_rerank": {"success": True, "data": {"passed_count": 1}}},
    }

    gap_resp = MagicMock()
    gap_resp.model_dump.return_value = {
        "knowledge_gaps": [{"gap": "missing longitudinal study"}],
    }

    hypo_resp = MagicMock()
    hypo_resp.model_dump.return_value = {
        "hypotheses": [{"hypothesis": "H1", "supporting_fact_ids": ["f1"]}],
    }

    lit_agent = MagicMock()
    lit_agent.mine.return_value = lit_resp
    gap_agent = MagicMock()
    gap_agent.analyze.return_value = gap_resp
    hypo_agent = MagicMock()
    hypo_agent.generate.return_value = hypo_resp

    lit = lit_agent.mine("proj", "rq", top_k=5, db=None, research_domain="FL")
    lit_dict = lit.model_dump()
    gap = gap_agent.analyze(
        research_question="rq",
        literature_facts=lit_dict.get("facts") or [],
        uncertain_points=lit_dict.get("uncertain_points") or [],
    )
    gap_dict = gap.model_dump()
    hypo = hypo_agent.generate(
        research_question="rq",
        knowledge_gaps=gap_dict.get("knowledge_gaps") or [],
        literature_facts=lit_dict.get("facts") or [],
    )
    hypo_dict = hypo.model_dump()

    assert lit_dict["facts"]
    assert gap_dict["knowledge_gaps"]
    assert hypo_dict["hypotheses"]
    lit_agent.mine.assert_called_once()
    gap_agent.analyze.assert_called_once()
    hypo_agent.generate.assert_called_once()
