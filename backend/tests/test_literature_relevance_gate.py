"""论文级相关性门控 + 查询改写单测。"""
from unittest.mock import MagicMock, patch

from app.services.literature_relevance_gate import (
    apply_relevance_gate,
    rewrite_search_queries,
    score_and_gate_papers,
)


def _settings(
    *,
    enabled=True,
    cutoff=6,
    use_mock=True,
    api_key="",
):
    s = MagicMock()
    s.LIT_RELEVANCE_GATE_ENABLED = enabled
    s.LIT_PAPER_SCORE_CUTOFF = cutoff
    s.USE_MOCK_LLM = use_mock
    s.QWEN_API_KEY = api_key
    return s


def test_gate_disabled_passes_all():
    papers = [
        {"title": "Unrelated Astronomy", "abstract": "stars and galaxies"},
        {"title": "Federated Learning", "abstract": "FL for healthcare"},
    ]
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=False),
    ):
        out = score_and_gate_papers("联邦学习跌倒检测", papers)
    assert out["enabled"] is False
    assert out["passed_count"] == 2
    assert all(p.get("gate_passed") for p in out["papers"])


def test_heuristic_gate_rejects_unrelated():
    papers = [
        {
            "title": "Deep Sky Survey of Quasars",
            "abstract": "We observe distant quasars with radio telescopes.",
            "verification_status": "verified",
        },
        {
            "title": "Federated Learning for Fall Detection",
            "abstract": "Federated learning improves fall detection with synthetic data.",
            "verification_status": "verified",
        },
    ]
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=True, cutoff=6),
    ):
        out = score_and_gate_papers(
            "federated learning synthetic data for elderly fall detection",
            papers,
        )
    assert out["enabled"] is True
    titles = [p["title"] for p in out["passed"]]
    assert any("Fall Detection" in t for t in titles)
    assert all("Quasar" not in t for t in titles)


def test_llm_gate_uses_structured_scores():
    papers = [
        {"title": "A", "abstract": "a"},
        {"title": "B", "abstract": "b"},
    ]
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=False, api_key="k", cutoff=6),
    ):
        with patch(
            "app.services.qwen_client.qwen_structured_chat",
            return_value={
                "papers": [
                    {"index": 0, "relevance_score": 2, "reason": "弱相关"},
                    {"index": 1, "relevance_score": 9, "reason": "强相关"},
                ]
            },
        ):
            out = score_and_gate_papers("test question about B", papers)
    assert out["passed_count"] == 1
    assert out["passed"][0]["title"] == "B"
    assert out["passed"][0]["relevance_score"] == 9.0


def test_gate_reuses_recommend_scores_without_llm():
    papers = [
        {
            "title": "A",
            "abstract": "a",
            "relevance_score": 2,
            "relevance_reason": "弱",
            "score_source": "llm_recommend",
        },
        {
            "title": "B",
            "abstract": "b",
            "relevance_score": 9,
            "relevance_reason": "强",
            "score_source": "llm_recommend",
        },
    ]
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=False, api_key="k", cutoff=6),
    ):
        with patch("app.services.qwen_client.qwen_structured_chat") as mock_chat:
            out = score_and_gate_papers("q", papers)
    mock_chat.assert_not_called()
    assert out["score_source"] == "recommend"
    assert out["passed_count"] == 1
    assert out["passed"][0]["title"] == "B"
    assert out["passed"][0]["relevance_reason"] == "强"


def test_rewrite_skips_llm_when_recommend_queries_present():
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=False, api_key="k"),
    ):
        with patch("app.services.qwen_client.qwen_structured_chat") as mock_chat:
            qs = rewrite_search_queries(
                "联邦学习合成数据跌倒检测挑战",
                "联邦学习",
                existing_queries=[
                    "federated synthetic fall detection",
                    "federated learning elderly care",
                ],
            )
    mock_chat.assert_not_called()
    assert len(qs) >= 2


def test_rewrite_queries_heuristic_when_mock():
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=True),
    ):
        qs = rewrite_search_queries(
            "联邦学习合成数据跌倒检测挑战",
            "联邦学习 / 智慧康养",
            existing_queries=["existing query"],
        )
    assert qs
    assert any("existing query" in q for q in qs)


def test_apply_relevance_gate_updates_rec_output():
    rec = {
        "papers": [
            {
                "title": "Federated synthetic fall data",
                "abstract": "federated learning synthetic data for fall detection",
                "verification_status": "verified",
            },
            {
                "title": "Cooking recipes",
                "abstract": "how to bake bread",
                "verification_status": "verified",
            },
        ],
        "search_queries": ["old"],
        "research_domain": "联邦学习",
    }
    with patch(
        "app.core.config.get_settings",
        return_value=_settings(enabled=True, use_mock=True, cutoff=5),
    ):
        gated = apply_relevance_gate(
            "联邦学习合成数据跌倒检测",
            rec,
            research_domain="联邦学习",
        )
    assert "gate_stats" in gated
    assert gated["gate_stats"]["enabled"] is True
    assert len(gated["papers"]) <= 2
    assert gated.get("search_queries")

