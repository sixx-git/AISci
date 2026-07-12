"""文献发现流水线单元测试 — Crawler + Selector"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.skills.literature.literature_discovery_pipeline import (
    LiteratureDiscoveryPipeline,
    build_generalized_queries,
    extract_core_concepts,
    filter_papers_by_llm_relevance,
    heuristic_expand_queries,
    normalize_api_search_query,
    passes_concept_filter,
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

    def test_normalize_api_search_query_strips_boolean(self):
        raw = '("vertical federated learning" OR VFL) AND ("label heterogeneity") AND IoT'
        norm = normalize_api_search_query(raw)
        self.assertNotIn("AND", norm.upper())
        self.assertNotIn("OR", norm.upper())
        self.assertIn("vertical federated learning", norm)
        self.assertIn("label heterogeneity", norm)
        self.assertIn("IoT", norm)

    def test_concept_filter_blocks_low_overlap(self):
        paper = {
            "title": "Privacy-Preserving Adversarial Transfer for EEG Decoding",
            "abstract": "EEG brain-computer interface privacy risks",
        }
        core = extract_core_concepts(
            "federated IoT heterogeneous labels non-IID vertical federated learning",
            keywords=["federated learning", "IoT", "label heterogeneity", "VFL"],
        )
        self.assertFalse(passes_concept_filter(paper, core))

    def test_concept_filter_allows_relevant_fl_paper(self):
        paper = {
            "title": "Vertical Federated Learning with Heterogeneous Labels in IoT",
            "abstract": "non-IID federated learning for IoT devices with label alignment",
        }
        core = extract_core_concepts(
            "federated IoT heterogeneous labels",
            keywords=["vertical federated learning", "non-IID"],
        )
        self.assertTrue(passes_concept_filter(paper, core))

    def test_concept_filter_allows_eeg_when_question_is_eeg(self):
        paper = {
            "title": "Privacy-Preserving EEG Decoding for Brain-Computer Interface",
            "abstract": "EEG BCI privacy-preserving adversarial training",
        }
        core = extract_core_concepts(
            "privacy-preserving EEG decoding brain-computer interface",
            keywords=["EEG", "BCI", "privacy"],
        )
        self.assertTrue(passes_concept_filter(paper, core))

    def test_build_generalized_queries_from_concepts(self):
        queries = build_generalized_queries(
            "联邦物联网标签异构联邦学习",
            keywords=["vertical federated learning", "non-IID", "IoT"],
        )
        self.assertGreaterEqual(len(queries), 2)
        self.assertTrue(all("AND" not in q.upper() for q in queries))

    @patch("app.services.qwen_client.qwen_structured_chat")
    def test_llm_relevance_gate_filters_irrelevant(self, mock_llm):
        mock_llm.return_value = {
            "reviews": [
                {"index": 0, "relevant": False, "reason": "EEG 与联邦物联网无关"},
                {"index": 1, "relevant": True, "reason": "直接讨论 VFL 与标签异构"},
            ],
        }
        papers = [
            {"title": "Privacy-Preserving EEG Decoding", "abstract": "brain-computer interface"},
            {"title": "Vertical Federated Learning with Heterogeneous Labels", "abstract": "IoT non-IID"},
        ]
        kept, meta = filter_papers_by_llm_relevance(
            papers,
            "federated IoT label heterogeneity",
            domain_hint="federated learning IoT",
        )
        self.assertEqual(len(kept), 1)
        self.assertIn("Vertical Federated", kept[0]["title"])
        self.assertEqual(meta.get("rejected"), 1)

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
