"""Phase 7 — Release Gate / 步骤观测 / Golden Corpus E2E"""
import asyncio
import csv
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.data_integration import build_figure_extraction_manifest
from app.services.data_acquisition_release_gate import evaluate_release_gate
from app.services.data_finder_bundle import build_analysis_bundle
from app.services.data_finder_coverage import build_coverage_report
from app.skills.data_finder.dataset_merge_skill import DatasetMergeSkill
from app.skills.data_finder.text_facts_extraction_skill import TextFactsExtractionSkill

FIXTURES = Path(__file__).parent / "fixtures" / "data_acquisition"


class TestReleaseGate(unittest.TestCase):
    def test_passes_with_merged_and_provenance(self):
        gate = evaluate_release_gate({
            "merged": {"row_count": 3, "merged_csv_path": "/tmp/m.csv"},
            "extracted_tables": [{"table_id": "t1"}, {"table_id": "t2"}],
            "provenance": [{"record_id": "t1"}, {"record_id": "t2"}],
            "figures": [],
            "coverage_report": {"completeness_score": 80},
            "data_acquisition": {"stats": {"gap_rounds": 1}},
        })
        self.assertTrue(gate["passed"])
        self.assertTrue(gate["ready_for_report"])

    def test_fails_without_merge(self):
        gate = evaluate_release_gate({"merged": {}, "extracted_tables": [], "figures": []})
        self.assertFalse(gate["passed"])
        self.assertIn("merged_csv", gate["failed_ids"])


class TestGoldenCorpusPipeline(unittest.TestCase):
    """Golden Corpus：fixture CSV join → bundle → release gate（无外网）。"""

    def test_fl_fixture_join_merge_and_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_a = str(FIXTURES / "fl_client_metrics.csv")
            csv_b = str(FIXTURES / "fl_client_f1.csv")
            self.assertTrue(os.path.exists(csv_a))

            tables = [
                {
                    "table_id": "t_metrics",
                    "csv_path": csv_a,
                    "source_title": "FL metrics",
                    "columns": ["client_id", "global_accuracy", "communication_cost_mb", "round"],
                },
                {
                    "table_id": "t_f1",
                    "csv_path": csv_b,
                    "source_title": "FL F1",
                    "columns": ["client_id", "f1_score", "round"],
                },
            ]
            alignments = [
                {
                    "table_id": "t_metrics",
                    "standard_columns": ["client_id", "global_accuracy", "communication_cost_mb", "round"],
                    "join_keys": ["client_id"],
                    "merge_strategy": "join",
                },
                {
                    "table_id": "t_f1",
                    "standard_columns": ["client_id", "f1_score", "round"],
                    "join_keys": ["client_id"],
                    "merge_strategy": "join",
                },
            ]
            skill = DatasetMergeSkill()
            merge_res = asyncio.run(skill.run(
                {
                    "tables": tables,
                    "alignments": alignments,
                    "provenance": [
                        {"record_id": "t_metrics", "source_type": "fixture"},
                        {"record_id": "t_f1", "source_type": "fixture"},
                    ],
                    "output_dir": tmp,
                    "merge_strategy": "join",
                },
                {},
            ))
            self.assertEqual(merge_res.data.get("row_count"), 3)
            merged_path = merge_res.data.get("merged_csv_path")
            self.assertTrue(merged_path and os.path.exists(merged_path))

            project_dir = os.path.join(tmp, "proj")
            os.makedirs(project_dir, exist_ok=True)
            results = {
                "project_mode": "federated_learning",
                "merged": merge_res.data,
                "extracted_tables": tables,
                "provenance": [
                    {"record_id": "t_metrics", "source_type": "fixture", "extraction_method": "golden"},
                    {"record_id": "t_f1", "source_type": "fixture", "extraction_method": "golden"},
                ],
                "figures": [{
                    "figure_id": "fig_golden_1",
                    "extraction_manifest": build_figure_extraction_manifest({
                        "figure_id": "fig_golden_1",
                        "caption": "Accuracy vs rounds",
                        "extraction_tier": "L2_rule_series",
                        "extraction_method": "rule_series",
                        "extraction_confidence": 0.5,
                        "review_status": "pending",
                    }),
                }],
                "data_spec": {
                    "entities_of_interest": ["client_id"],
                    "target_variables": ["global_accuracy", "f1_score"],
                },
            }
            coverage = build_coverage_report(results, documents_count=1)
            results["coverage_report"] = coverage
            bundle = build_analysis_bundle("golden-proj", project_dir, results, coverage_report=coverage)
            results["analysis_bundle"] = bundle

            gate = evaluate_release_gate(results, config={"require_bundle_ready": True})
            self.assertTrue(bundle.get("ready"), bundle.get("reason"))
            self.assertTrue(gate["passed"], gate.get("failed_ids"))

            with open(merged_path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            self.assertIn("client_id", rows[0])

    def test_text_facts_from_golden_snippet(self):
        snippet = (FIXTURES / "paper_results_snippet.txt").read_text(encoding="utf-8")
        skill = TextFactsExtractionSkill()
        res = asyncio.run(skill.run(
            {
                "documents": [{"id": "doc1", "title": "FL", "raw_text": snippet}],
                "target_variables": ["accuracy", "f1_score"],
            },
            {},
        ))
        self.assertGreaterEqual(res.data.get("count", 0), 1)


@pytest.mark.integration
class TestDataAcquisitionStepTiming(unittest.TestCase):
    def test_acquire_records_duration_ms(self):
        from app.services.data_finder_service import DataFinderService

        mock_db = MagicMock()
        svc = DataFinderService(mock_db)
        svc._project_dir = MagicMock(return_value=tempfile.mkdtemp())
        svc.load_results = MagicMock(return_value={})
        svc.save_results = MagicMock()
        svc.run_dataset_discovery = AsyncMock(return_value={"external_candidates": [{"dataset_name": "ds1"}]})
        svc.run_search_quick = svc.run_dataset_discovery
        svc.run_search = AsyncMock(return_value={"external_candidates": []})
        svc.run_fetch_supplementary = AsyncMock(return_value={})
        svc.run_extract_tables = AsyncMock(return_value={"extracted_tables": []})
        svc.run_gap_loop = AsyncMock(return_value=[])

        final = asyncio.run(svc.run_data_acquisition(
            "proj-timing",
            "test question",
            gap_options={"enable_gap_search": False},
            auto_import=False,
        ))
        details = final["data_acquisition"]["step_details"]
        self.assertIn("duration_ms", details["discover"])
        self.assertIsNone(details["discover"]["error_code"])
        self.assertTrue(details["extract"].get("skipped"))
        self.assertEqual(final["data_acquisition"]["mode"], "dataset_discovery")
        self.assertIn("total_duration_ms", final["data_acquisition"]["stats"])
        self.assertIn("release_gate", final)
        svc.run_dataset_discovery.assert_awaited_once()
        svc.run_search.assert_not_awaited()

    def test_acquire_full_mode_uses_heavy_discover(self):
        from app.services.data_finder_service import DataFinderService

        mock_db = MagicMock()
        svc = DataFinderService(mock_db)
        svc._project_dir = MagicMock(return_value=tempfile.mkdtemp())
        svc._resolve_acquisition_mode = MagicMock(return_value="full")
        svc.load_results = MagicMock(return_value={})
        svc.save_results = MagicMock()
        svc.run_search = AsyncMock(return_value={"external_candidates": []})
        svc.run_dataset_discovery = AsyncMock(return_value={"external_candidates": []})
        svc.run_search_quick = AsyncMock(return_value={"external_candidates": []})
        svc.run_fetch_supplementary = AsyncMock(return_value={})
        svc.run_extract_tables = AsyncMock(return_value={"extracted_tables": []})
        svc.run_gap_loop = AsyncMock(return_value=[])

        final = asyncio.run(svc.run_data_acquisition(
            "proj-full",
            "test question",
            gap_options={"acquisition_mode": "full", "enable_gap_search": False},
            auto_import=False,
        ))
        self.assertEqual(final["data_acquisition"]["mode"], "full")
        svc.run_search.assert_awaited_once()
        svc.run_dataset_discovery.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
