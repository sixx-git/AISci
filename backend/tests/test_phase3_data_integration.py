"""Phase 3 — DataSpec coverage / hints / report manifest"""
import unittest

from app.schemas.data_integration import apply_data_spec_hints, empty_data_spec, parse_comma_list
from app.services.data_finder_coverage import build_data_spec_coverage, build_coverage_report
from app.agents.report_generation_agent import ReportGenerationAgent


class TestDataSpecHints(unittest.TestCase):
    def test_parse_comma_list(self):
        self.assertEqual(parse_comma_list("a, b;c"), ["a", "b", "c"])

    def test_apply_hints_merges_lists(self):
        spec = empty_data_spec("q", "general")
        spec["entities_of_interest"] = ["sample_id"]
        merged = apply_data_spec_hints(spec, {
            "entities_of_interest": ["patient_id"],
            "target_variables": "accuracy, f1",
            "merge_strategy_hint": "join",
        })
        self.assertIn("sample_id", merged["entities_of_interest"])
        self.assertIn("patient_id", merged["entities_of_interest"])
        self.assertIn("accuracy", merged["target_variables"])
        self.assertEqual(merged["merge_strategy_hint"], "join")


class TestDataSpecCoverage(unittest.TestCase):
    def test_entity_and_target_hits(self):
        spec = {
            "scenario": "general",
            "entities_of_interest": ["patient_id"],
            "target_variables": ["accuracy"],
            "column_synonyms": {},
            "preferred_sources": ["paper_table"],
        }
        results = {
            "merged": {"columns": ["patient_id", "accuracy", "_provenance_table_id"]},
            "alignments": [{"standard_columns": ["patient_id", "accuracy"]}],
            "extracted_tables": [{"table_id": "t1"}],
            "figures": [],
            "external_candidates": [],
        }
        cov = build_data_spec_coverage(spec, results)
        self.assertEqual(cov["data_spec_score"], 100.0)
        self.assertEqual(cov["entities_hit"], ["patient_id"])
        self.assertEqual(cov["targets_hit"], ["accuracy"])

    def test_coverage_report_includes_data_spec(self):
        report = build_coverage_report(
            {
                "project_mode": "general",
                "data_spec": {
                    "entities_of_interest": ["id"],
                    "target_variables": ["score"],
                },
                "merged": {"columns": ["id", "score"], "merged_csv_path": "/x.csv", "row_count": 1},
                "alignments": [{"standard_columns": ["id", "score"]}],
                "extracted_tables": [{}],
                "external_candidates": [{}],
                "paper_extractions": [{"data_links": ["http://x"]}],
            },
            documents_count=1,
        )
        self.assertIn("data_spec_coverage", report)
        self.assertIsNotNone(report["data_spec_coverage"].get("data_spec_score"))


class TestReportManifestEnrichment(unittest.TestCase):
    def test_enrich_includes_manifest_and_spec_score(self):
        agent = ReportGenerationAgent()
        result = {
            "chapters": {
                "datasets": "",
                "source": "",
                "results": "",
            },
        }
        df = {
            "data_spec": {
                "scenario": "general",
                "entities_of_interest": ["client_id"],
                "target_variables": ["accuracy"],
            },
            "figures": [{
                "figure_id": "fig_1",
                "extraction_manifest": {
                    "figure_id": "fig_1",
                    "identification": {"figure_number": "1", "chart_type": "line"},
                    "extraction": {"tier": "L3_vlm", "method": "vlm", "confidence": 0.7, "limitations": ["低置信"]},
                    "validation": {"status": "pending"},
                },
            }],
            "coverage_report": {
                "completeness_score": 80,
                "data_spec_coverage": {"data_spec_score": 50, "entities_hit": [], "entities_requested": ["client_id"],
                                       "targets_hit": [], "targets_requested": ["accuracy"]},
            },
            "provenance": [{
                "source_type": "paper_table",
                "source_title": "Paper A",
                "page": 3,
                "table_or_figure": "t1",
                "extraction_method": "pymupdf",
                "confidence": 0.9,
                "data_citation_id": "cite_abc",
            }],
            "merged": {"row_count": 10, "merged_csv_path": "/tmp/m.csv", "columns": ["a", "b"]},
        }
        out = agent._enrich_report_with_data_finder(result, df)
        self.assertIn("DataSpec", out["chapters"]["datasets"])
        self.assertIn("extraction manifest", out["chapters"]["source"])
        self.assertIn("cite_abc", out["chapters"]["source"])
        self.assertEqual(out["data_finder_summary"]["data_spec_score"], 50)
        self.assertEqual(out["data_finder_summary"]["figures_with_manifest"], 1)
        results = out["chapters"]["results"]
        self.assertIsInstance(results, dict)
        self.assertTrue(results.get("simulated_results"))

    def test_enrich_fits_upload_in_datasets_and_results(self):
        agent = ReportGenerationAgent()
        result = {"chapters": {"datasets": "已有数据集说明", "source": "", "results": {}}}
        df = {
            "extracted_tables": [{
                "source_title": "JWST NIRSpec GS-9209",
                "table_id": "fits_0",
                "row_count": 3813,
                "extraction_method": "fits_data",
            }],
            "merged": {
                "row_count": 3813,
                "merged_csv_path": "/tmp/merged.csv",
                "columns": ["slice_index", "mean", "std", "min", "max"],
            },
            "provenance": [],
            "coverage_report": {},
        }
        out = agent._enrich_report_with_data_finder(result, df)
        ds = out["chapters"]["datasets"]
        self.assertIn("FITS", ds)
        self.assertIn("3813", ds)
        sim = out["chapters"]["results"].get("simulated_results") or []
        self.assertTrue(any("3813" in str(x) for x in sim))


if __name__ == "__main__":
    unittest.main()
