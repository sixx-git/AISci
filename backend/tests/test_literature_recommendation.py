"""网页式文献推荐测试。"""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.literature_recommendation_service import (
    llm_recommend_papers,
    run_literature_recommendation,
)
from app.services.literature_search_utils import titles_match
from app.services.paper_verification_service import verify_recommended_paper

GOLDEN_QUESTION = (
    "对于联邦智慧康养场景，使用数据生成的方式补充无法直接采集的老年人跌倒等危险场景，"
    "会带来什么新的挑战？"
)
GOLDEN_DOMAIN = "联邦学习 / 智慧康养 / 合成数据"


def test_llm_recommend_prompt_inputs_only_question_and_domain():
    with patch("app.services.literature_recommendation_service.qwen_structured_chat") as mock_chat:
        mock_chat.return_value = {
            "subtopics": [{"label": "sim-to-real", "summary": "域偏差"}],
            "papers": [],
            "rationale": "test",
            "search_queries": ["federated synthetic fall"],
        }
        with patch("app.services.literature_recommendation_service.get_settings") as mock_settings:
            mock_settings.return_value.USE_MOCK_LLM = False
            mock_settings.return_value.QWEN_API_KEY = "key"
            out = llm_recommend_papers(GOLDEN_QUESTION, GOLDEN_DOMAIN, max_papers=8)
        assert out["search_queries"]
        prompt_arg = mock_chat.call_args.kwargs.get("prompt") or mock_chat.call_args[1].get("prompt", "")
        assert GOLDEN_QUESTION[:20] in prompt_arg or "联邦" in prompt_arg
        assert "智慧康养" in prompt_arg or GOLDEN_DOMAIN.split("/")[0].strip() in prompt_arg


def test_titles_match():
    assert titles_match(
        "Federated Learning with GAN-Based Data Synthesis",
        "Federated Learning with GAN Based Data Synthesis for Non-IID Clients",
    )
    # 放宽后：核心词重叠仍应通过
    assert titles_match(
        "Small gaps between primes",
        "Small gaps between primes: Bounded gaps between consecutive primes",
    )


def test_verify_soft_title_match_becomes_partial():
    paper = {
        "title": "FedProto: Federated Prototype Learning across Heterogeneous Clients",
        "authors": ["A"],
        "doi": "10.1234/fedproto",
    }

    async def _run():
        with patch(
            "app.services.paper_verification_service._lookup_openalex_by_doi",
            new_callable=AsyncMock,
            return_value={
                "title": "FedProto: Federated Prototype Learning Across Heterogeneous Clients",
                "abstract": "We propose FedProto for federated learning with heterogeneous label spaces.",
                "doi": "10.1234/fedproto",
            },
        ):
            return await verify_recommended_paper(paper)

    result = asyncio.run(_run())
    assert result["verification_status"] in ("verified", "partial")
    assert "FedProto" in (result.get("title") or "")


def test_verify_rejects_title_mismatch_on_arxiv():
    paper = {
        "title": "Feature Alignment in Vertical Federated Learning",
        "authors": ["A"],
        "arxiv_id": "2105.06188",
    }

    async def _run():
        with patch(
            "app.services.paper_verification_service._lookup_arxiv_by_id",
            new_callable=AsyncMock,
            return_value={
                "title": "SizeNet: Object Recognition Based on Real Size",
                "abstract": "object recognition",
                "arxiv_id": "2105.06188",
            },
        ):
            return await verify_recommended_paper(paper)

    result = asyncio.run(_run())
    assert result["verification_status"] == "unverified"
    # 错文摘要不得写入推荐条目
    assert "object recognition" not in (result.get("abstract") or "")


@patch("app.services.literature_recommendation_service.verify_recommended_papers", new_callable=AsyncMock)
@patch("app.services.literature_recommendation_service.llm_recommend_papers")
def test_run_literature_recommendation_web_flow(mock_llm, mock_verify):
    mock_llm.return_value = {
        "papers": [
            {
                "title": "Federated GAN for fall detection in elderly care with synthetic data",
                "authors": ["Li"],
                "year": 2023,
                "doi": "10.1234/test",
                "subtopic_labels": ["sim-to-real"],
                "relevance_reason": "covers federated synthetic data and fall detection",
            }
        ],
        "subtopics": [{"label": "sim-to-real", "summary": "域偏差"}],
        "rationale": "按子主题推荐",
        "search_queries": ["federated learning synthetic fall detection"],
    }
    mock_verify.return_value = [
        {
            "title": "Federated GAN for fall detection in elderly care with synthetic data",
            "verification_status": "verified",
            "abstract": "federated learning synthetic fall detection elderly",
        }
    ]

    result = asyncio.run(
        run_literature_recommendation(
            GOLDEN_QUESTION,
            GOLDEN_DOMAIN,
            supplement_api=False,
        )
    )

    assert result["discovery_mode"] == "llm_recommend_web_v3"
    assert result["research_domain"] == GOLDEN_DOMAIN
    assert len(result["subtopics"]) >= 1
    assert result["verified_count"] == 1
    mock_llm.assert_called_once_with(GOLDEN_QUESTION, GOLDEN_DOMAIN, max_papers=mock_llm.call_args.kwargs.get("max_papers", 12))
