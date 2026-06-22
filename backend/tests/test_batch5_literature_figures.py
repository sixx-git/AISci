"""Batch 5 — 图表分层抽取 / 文献自动入库 / 外部 API"""
import unittest

from app.core.figure_extraction import extract_rule_series_from_caption, write_figure_series_csv
from app.services.data_finder_gap_search import build_gap_search_queries
from app.services.literature_corpus_service import _score_paper_relevance, ensure_corpora_from_search
from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill


class TestBatch5FigureExtraction(unittest.TestCase):
    def test_rule_series_from_caption(self):
        rows = extract_rule_series_from_caption(
            "FedAvg vs FedProx accuracy 82.5% and 79.1%",
            ["FedAvg", "FedProx"],
        )
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(rows[0].get("series"), "FedAvg")

    def test_write_figure_csv(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fig.csv")
            write_figure_series_csv(
                path,
                [{"series": "A", "value": 1.0, "_provenance_extraction_method": "rule_series", "_confidence": 0.5}],
                {"figure_id": "fig_1", "source_title": "Test"},
            )
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            self.assertIn("figure_id", content)
            self.assertIn("A", content)


class TestBatch5LiteratureCorpus(unittest.TestCase):
    def test_score_paper_relevance(self):
        paper = {"title": "Federated learning privacy", "abstract": "We study federated learning", "arxiv_id": "1234.5678"}
        score = _score_paper_relevance(paper, "federated learning privacy")
        self.assertGreater(score, 2.0)

    def test_ensure_corpora_empty(self):
        result = ensure_corpora_from_search("proj", "query", None, db=None)
        self.assertEqual(result.get("imported", 0), 0)


class TestBatch5ExternalApi(unittest.TestCase):
    def test_zenodo_search_structure(self):
        out = ExternalDatasetSearchSkill._search_zenodo("__unlikely_query_xyz_no_results__")
        self.assertIn("results", out)

    def test_pubmed_geo_structure(self):
        out = ExternalDatasetSearchSkill._search_pubmed_geo("gene expression")
        self.assertIn("results", out)


if __name__ == "__main__":
    unittest.main()
