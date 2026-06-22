"""Batch 3 — 清洗 / Coverage / Analysis Bundle"""
import csv
import os
import tempfile
import unittest

from app.core.data_cleaning import clean_csv_file, infer_csv_schema
from app.services.data_finder_bundle import build_analysis_bundle
from app.services.data_finder_coverage import build_coverage_report


class TestBatch3DataCleaning(unittest.TestCase):
    def test_clean_csv_dedup_and_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "raw.csv")
            dst = os.path.join(tmp, "cleaned.csv")
            with open(src, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["x", "y", "_provenance_table_id"])
                w.writerow(["1", "2", "t1"])
                w.writerow(["1", "2", "t1"])
                w.writerow(["3", "", "t2"])
            report = clean_csv_file(src, dst)
            self.assertEqual(report["rows_before"], 3)
            self.assertEqual(report["rows_after"], 2)
            self.assertTrue(os.path.exists(dst))
            self.assertIn("_cleaning_action", open(dst, encoding="utf-8-sig").readline())

    def test_infer_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.csv")
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["a", "b"])
                w.writerow(["1", "2"])
            schema = infer_csv_schema(path)
            self.assertEqual(schema["column_count"], 2)


class TestBatch3Coverage(unittest.TestCase):
    def test_coverage_score(self):
        report = build_coverage_report(
            {
                "project_mode": "general",
                "paper_extractions": [{"data_links": ["http://x"]}],
                "extracted_tables": [{"table_id": "t1"}],
                "alignments": [{"standard_columns": ["x"]}],
                "merged": {"merged_csv_path": "/tmp/x.csv", "row_count": 10, "columns": ["x"]},
                "external_candidates": [{"name": "hf"}],
                "data_requirements": {"dataset_keywords": ["accuracy"]},
            },
            documents_count=2,
        )
        self.assertGreaterEqual(report["completeness_score"], 50)
        self.assertIn("domain_checklist", report)


class TestBatch3Bundle(unittest.TestCase):
    def test_build_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            merged_dir = os.path.join(tmp, "merged")
            os.makedirs(merged_dir)
            csv_path = os.path.join(merged_dir, "m.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["method", "accuracy"])
                w.writerow(["A", "0.9"])
            results = {
                "merged": {
                    "merge_id": "merged_test",
                    "merged_csv_path": csv_path,
                    "cleaned_csv_path": csv_path,
                    "row_count": 1,
                    "columns": ["method", "accuracy"],
                },
                "provenance": [{"record_id": "r1", "source_title": "Paper"}],
            }
            cov = build_coverage_report(results, documents_count=1)
            meta = build_analysis_bundle("proj1", tmp, results, coverage_report=cov)
            self.assertTrue(meta.get("ready"))
            self.assertTrue(os.path.exists(meta["bundle_zip_path"]))


if __name__ == "__main__":
    unittest.main()
