"""Phase 6 — 图表 L4 数字化 / crop bbox / 正文 L1 事实抽取"""
import asyncio
import os
import tempfile
import unittest

from app.core.figure_digitization import (
    infer_tier_from_digitization,
    series_json_to_rows,
    validate_digitized_series,
)
from app.core.figure_extraction import write_figure_series_csv
from app.schemas.data_integration import build_figure_extraction_manifest
from app.skills.data_finder.text_facts_extraction_skill import TextFactsExtractionSkill


class TestFigureDigitization(unittest.TestCase):
    def test_validate_l4_points(self):
        payload = {
            "series": [{
                "name": "A",
                "points": [{"x": i, "y": 0.5 + i * 0.01} for i in range(12)],
            }],
        }
        checks, confidence, count = validate_digitized_series(payload)
        self.assertGreaterEqual(count, 10)
        self.assertIn("min_points_ok", checks)
        tier = infer_tier_from_digitization(
            method="vlm_digitize",
            confidence=confidence,
            points_count=count,
            checks=checks,
        )
        self.assertEqual(tier, "L4_digitize")

    def test_series_json_to_rows_has_xy(self):
        rows = series_json_to_rows({
            "series": [{"name": "B", "points": [{"x": 1, "y": 0.9}, {"x": 2, "y": 0.95}]}],
        })
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["x"], 1)
        self.assertEqual(rows[0]["y"], 0.9)

    def test_manifest_v2_fields(self):
        manifest = build_figure_extraction_manifest({
            "figure_id": "f1",
            "caption": "Accuracy",
            "extraction_method": "vlm_digitize",
            "extraction_tier": "L4_digitize",
            "extraction_confidence": 0.8,
            "bbox": [10, 20, 100, 200],
            "crop_method": "block_proximity",
            "digitization_checks": ["json_schema_ok", "min_points_ok"],
            "points_count": 12,
            "schema_version": "figure_series_v2",
            "image_path": "/tmp/x.png",
        })
        self.assertEqual(manifest["identification"]["crop_method"], "block_proximity")
        self.assertEqual(manifest["extraction"]["points_count"], 12)
        self.assertIn("auto_checks", manifest["validation"])

    def test_csv_writes_xy_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fig.csv")
            write_figure_series_csv(path, [
                {"series": "A", "x": 1, "y": 0.5, "value": 0.5, "unit": "digitized"},
            ], {"figure_id": "f1", "figure_number": "1"})
            with open(path, encoding="utf-8-sig") as f:
                header = f.readline()
            self.assertIn("x", header)
            self.assertIn("y", header)


class TestTextFactsExtraction(unittest.TestCase):
    def test_extracts_numeric_sentence_with_target(self):
        skill = TextFactsExtractionSkill()
        doc_text = """
        Methods
        We trained the model with FedAvg for 100 rounds.
        Results
        The global accuracy reached 92.5% on the test set.
        Table 2 summarizes F1 scores across clients.
        """
        res = asyncio.run(skill.run(
            {
                "documents": [{
                    "id": "d1",
                    "title": "FL Paper",
                    "raw_text": doc_text,
                }],
                "target_variables": ["accuracy", "f1_score"],
            },
            {},
        ))
        facts = res.data.get("text_facts") or []
        self.assertTrue(len(facts) >= 1)
        self.assertTrue(any("accuracy" in str(f.get("matched_targets")) for f in facts))
        self.assertEqual(facts[0]["extraction_tier"], "L1_text_fact")

    def test_skips_irrelevant_when_targets_set(self):
        skill = TextFactsExtractionSkill()
        res = asyncio.run(skill.run(
            {
                "documents": [{
                    "id": "d1",
                    "raw_text": "Results: we used 10 participants in the survey.",
                }],
                "target_variables": ["global_accuracy"],
            },
            {},
        ))
        self.assertEqual(res.data.get("count"), 0)


if __name__ == "__main__":
    unittest.main()
