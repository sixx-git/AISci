"""文献发现流水线单元测试 — Crawler + Selector"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.skills.literature.literature_discovery_pipeline import (
    LiteratureDiscoveryPipeline,
    heuristic_expand_queries,
    score_paper_relevance,
)


class TestLiteratureDiscoveryPipeline(unittest.IsolatedAsyncioTestCase):
    def test_heuristic_expand_queries_dedup(self):
        queries = heuristic_expand_queries(
            "纳米机器人在肿瘤靶向治疗中的应用",
            keywords=["nanorobot", "cancer therapy", "drug delivery"],
        )
        self.assertGreaterEqual(len(queries), 2)
        self.assertEqual(len(queries), len(set(q.lower() for q in queries)))

    def test_score_paper_relevance_title_boost(self):
        paper = {
            "title": "Nanorobots for targeted cancer therapy",
            "abstract": "We study nanorobot drug delivery systems",
            "arxiv_id": "2401.00001",
            "citation_count": 120,
        }
        score = score_paper_relevance(
            paper,
            "nanorobot cancer therapy",
            ["drug delivery", "targeted therapy"],
        )
        self.assertGreater(score, 4.0)

    def test_score_paper_relevance_low_match(self):
        paper = {"title": "Quantum computing benchmarks", "abstract": "qubits"}
        score = score_paper_relevance(paper, "nanorobot cancer", ["nanorobot"])
        self.assertLess(score, 1.0)

    @patch("app.skills.literature.literature_discovery_pipeline.expand_citations_openalex")
    async def test_pipeline_run_merges_search_results(self, mock_cite_expand):
        mock_cite_expand.return_value = ([], [])

        pipeline = LiteratureDiscoveryPipeline(sources=["arxiv"])
        mock_skill = MagicMock()
        mock_skill._deduplicate_papers.side_effect = lambda papers: (papers, 0)
        mock_skill.run = AsyncMock(
            side_effect=[
                MagicMock(
                    success=True,
                    data={"papers": [{"title": "Paper A", "abstract": "nanorobot", "source": "arxiv"}]},
                ),
                MagicMock(
                    success=True,
                    data={"papers": [{"title": "Paper B", "abstract": "cancer", "source": "arxiv"}]},
                ),
            ]
        )
        pipeline.search_skill = mock_skill

        with patch(
            "app.skills.literature.literature_discovery_pipeline.expand_queries_llm",
            return_value=["nanorobot cancer", "drug delivery tumor"],
        ):
            result = await pipeline.run(
                "nanorobot cancer therapy",
                use_llm_expand=True,
                expand_citations=False,
            )

        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["queries"]), 2)
        self.assertEqual(mock_skill.run.await_count, 2)


if __name__ == "__main__":
    unittest.main()
