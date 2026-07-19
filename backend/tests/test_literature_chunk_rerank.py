"""Chunk RCS 打分截断单测。"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.skills.literature.literature_chunk_rerank_skill import (
    rerank_search_results,
    score_chunk,
)


def _settings(*, enabled=True, cutoff=5, use_mock=True, api_key=""):
    s = MagicMock()
    s.LIT_RELEVANCE_GATE_ENABLED = enabled
    s.LIT_CHUNK_SCORE_CUTOFF = cutoff
    s.USE_MOCK_LLM = use_mock
    s.QWEN_API_KEY = api_key
    return s


def test_rerank_disabled_keeps_top_k():
    chunks = [
        SimpleNamespace(
            chunk_id=f"c{i}",
            content=f"text {i}",
            source_title="t",
            relevance_score=None,
            context_summary=None,
        )
        for i in range(5)
    ]
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=False),
    ):
        kept, stats = rerank_search_results("q", chunks, keep_top_k=2)
    assert stats["enabled"] is False
    assert len(kept) == 2


def test_heuristic_rerank_drops_unrelated():
    chunks = [
        SimpleNamespace(
            chunk_id="bad",
            content="Quasar luminosity functions in radio astronomy surveys.",
            source_title="Astronomy",
            relevance_score=None,
            context_summary=None,
        ),
        SimpleNamespace(
            chunk_id="good",
            content="Federated learning with synthetic data improves fall detection accuracy.",
            source_title="FL Fall",
            relevance_score=None,
            context_summary=None,
        ),
    ]
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=True, cutoff=5),
    ):
        kept, stats = rerank_search_results(
            "federated learning synthetic data fall detection",
            chunks,
            keep_top_k=10,
        )
    assert stats["enabled"] is True
    ids = [c.chunk_id for c in kept]
    assert "good" in ids
    assert "bad" not in ids


def test_llm_score_chunk_uses_structured_output():
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=False, api_key="k"),
    ):
        with patch(
            "app.services.qwen_client.qwen_structured_chat",
            return_value={"summary": "relevant passage", "relevance_score": 8},
        ):
            summary, score = score_chunk("question", "chunk text", "title")
    assert summary == "relevant passage"
    assert score == 8.0
