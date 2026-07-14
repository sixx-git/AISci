"""Phase 5 — 文献发现 / 连接器矩阵 / 复核 re-merge / 来源可用性"""
import asyncio
import unittest
from unittest.mock import patch

from app.services.data_finder_coverage import build_coverage_report, build_source_availability
from app.services.data_sources.base import normalize_legacy_candidate
from app.services.external_dataset_import_service import _rank_import_candidates
from app.services.literature_discovery_adapter import should_auto_discover_literature
from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill


class TestLiteratureDiscoveryGate(unittest.TestCase):
    def test_auto_when_few_docs_default(self):
        self.assertTrue(should_auto_discover_literature(0, {}))
        self.assertTrue(should_auto_discover_literature(2, {}))
        self.assertFalse(should_auto_discover_literature(5, {}))

    def test_explicit_off(self):
        cfg = {"data_acquisition": {"auto_literature_discovery": False}}
        self.assertFalse(should_auto_discover_literature(0, cfg))

    def test_explicit_on(self):
        cfg = {"data_acquisition": {"auto_literature_discovery": True}}
        self.assertTrue(should_auto_discover_literature(10, cfg))


class TestNormalizeLegacyCandidate(unittest.TestCase):
    def test_kaggle_catalog_only(self):
        c = normalize_legacy_candidate({
            "source_platform": "Kaggle (curated index)",
            "dataset_name": "titanic",
        })
        self.assertEqual(c["availability"], "catalog_only")
        self.assertFalse(c["import_supported"])

    def test_openalex_metadata_only(self):
        c = normalize_legacy_candidate({
            "source_platform": "OpenAlex",
            "dataset_name": "Some paper",
        })
        self.assertEqual(c["availability"], "metadata_only")
        self.assertFalse(c["import_supported"])

    def test_hf_importable(self):
        c = normalize_legacy_candidate({
            "source_platform": "HuggingFace Datasets",
            "dataset_name": "org/ds",
            "url": "https://huggingface.co/datasets/org/ds",
        })
        self.assertEqual(c["availability"], "search_and_import")
        self.assertTrue(c["import_supported"])


class TestImportRanking(unittest.TestCase):
    def test_skips_catalog_and_metadata(self):
        ranked = _rank_import_candidates([
            {"source_platform": "Kaggle", "dataset_name": "a", "confidence": 0.9},
            {"source_platform": "OpenAlex", "dataset_name": "b", "confidence": 0.9},
            {"source_platform": "HuggingFace Datasets", "dataset_name": "org/ds", "confidence": 0.7},
        ])
        self.assertEqual(len(ranked), 1)
        self.assertIn("huggingface", ranked[0]["source_platform"].lower())


class TestSourceAvailability(unittest.TestCase):
    def test_counts_by_availability(self):
        report = build_source_availability([
            {"source_platform": "HF", "availability": "search_and_import", "import_supported": True},
            {"source_platform": "Kaggle", "availability": "catalog_only", "import_supported": False},
            {"source_platform": "OpenAlex", "availability": "metadata_only", "import_supported": False},
        ])
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["importable_count"], 1)
        self.assertEqual(report["catalog_only_count"], 1)
        self.assertEqual(report["metadata_only_count"], 1)

    def test_coverage_honest_external_gap(self):
        cov = build_coverage_report(
            {
                "project_mode": "general",
                "external_candidates": [
                    {"source_platform": "OpenAlex", "availability": "metadata_only", "import_supported": False},
                ],
                "paper_extractions": [],
                "extracted_tables": [],
                "alignments": [],
                "merged": {},
            },
            documents_count=1,
        )
        self.assertFalse(cov["domain_checklist"][5]["hit"])
        self.assertTrue(any("不可自动导入" in g for g in cov["gaps"]))


class TestExternalSkillScope(unittest.TestCase):
    def test_skill_excludes_hf_zenodo_kaggle(self):
        skill = ExternalDatasetSearchSkill()
        with patch.object(skill, "_search_openalex", return_value={"results": []}), patch.object(
            skill, "_search_pubmed_geo", return_value={"results": []},
        ):
            res = asyncio.run(skill.run({"research_question": "test"}, {}))
        self.assertIn("openalex", res.data.get("live_apis", []))
        self.assertIn("registry_sources", res.data)
        self.assertNotIn("huggingface", res.data.get("live_apis", []))


if __name__ == "__main__":
    unittest.main()
