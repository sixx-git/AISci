"""文献入库阈值与统计字段回归测试。"""
from unittest.mock import MagicMock, patch

import pytest

from app.agents.literature_mining_agent import LiteratureMiningAgent, LiteratureMiningResponse
from app.services.literature_corpus_service import ensure_corpora_from_search
from app.skills.literature.literature_discovery_pipeline import filter_papers_by_llm_relevance


def test_filter_papers_llm_fallback_on_all_reject():
    papers = [
        {"title": "Federated learning privacy IoT", "abstract": "federated learning privacy"},
        {"title": "Vertical federated learning healthcare", "abstract": "vertical federated"},
    ]
    scored = [(2.5, papers[0]), (2.1, papers[1])]

    with patch(
        "app.services.qwen_client.qwen_structured_chat",
        return_value={"reviews": [{"index": 0, "relevant": False, "reason": "x"}, {"index": 1, "relevant": False, "reason": "y"}]},
    ):
        kept, meta = filter_papers_by_llm_relevance(
            papers,
            "federated learning privacy IoT",
            scored_fallback=scored,
            min_keep=2,
            high_score_threshold=1.8,
        )

    assert len(kept) == 2
    assert meta.get("fallback") == "high_score"


def test_apply_import_stats_sets_counts():
    agent = LiteratureMiningAgent()
    response = LiteratureMiningResponse()
    discovery = {"papers": [{"title": "A"}, {"title": "B"}], "candidate_count": 2}
    corpus = {"imported": 1, "selected_count": 2, "candidate_count": 2}

    updated = agent._apply_import_stats(
        response,
        discovery_output=discovery,
        corpus_meta=corpus,
    )

    assert updated.literature_search_count == 2
    assert updated.literature_import_count == 1
    assert updated.literature_selected_count == 2
    assert updated.imported_documents == 1


def test_ensure_corpora_scores_without_db():
    papers = [
        {
            "title": "Federated Learning for Smart Healthcare",
            "abstract": "We study federated learning and privacy in healthcare IoT settings.",
            "arxiv_id": "2401.00001",
            "source": "arxiv",
        },
        {
            "title": "Unrelated quantum chemistry review",
            "abstract": "molecular dynamics simulation",
            "source": "openalex",
        },
    ]
    result = ensure_corpora_from_search(
        "proj",
        "federated learning privacy healthcare IoT",
        {"papers": papers},
        db=None,
    )
    assert result.get("imported", 0) == 0
    assert result.get("scored_count", 0) >= 1
