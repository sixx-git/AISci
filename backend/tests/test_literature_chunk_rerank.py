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
    s.LIT_RCS_BATCH_SIZE = 12
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


def test_rerank_uses_batch_llm_once_for_many_chunks():
    chunks = [
        SimpleNamespace(
            chunk_id=f"c{i}",
            content=f"federated learning synthetic data chunk {i}",
            source_title=f"t{i}",
            relevance_score=None,
            context_summary=None,
        )
        for i in range(8)
    ]
    calls = {"n": 0}

    def _fake_chat(**kwargs):
        calls["n"] += 1
        schema = kwargs.get("schema_example") or {}
        if "chunks" in schema:
            return {
                "chunks": [
                    {"index": i, "summary": f"s{i}", "relevance_score": 8 if i % 2 == 0 else 2}
                    for i in range(8)
                ]
            }
        return {"summary": "x", "relevance_score": 5}

    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=False, api_key="k", cutoff=5),
    ):
        with patch("app.services.qwen_client.qwen_structured_chat", side_effect=_fake_chat):
            kept, stats = rerank_search_results("federated learning", chunks, keep_top_k=10)
    assert calls["n"] == 1
    assert stats["scoring_mode"] == "llm_batch"
    assert stats["llm_batches"] == 1
    assert all(c.chunk_id.startswith("c") and int(c.chunk_id[1:]) % 2 == 0 for c in kept)
