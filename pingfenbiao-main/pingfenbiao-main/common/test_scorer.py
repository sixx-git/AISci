"""
Scorer 单元测试 — 无需 API Key，使用 mock LLM。

运行:
  python common/test_scorer.py
  或 cd rubric-auto-gen && python ../common/test_scorer.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
GEN1 = ROOT / "rubric-auto-gen"
sys.path.insert(0, str(GEN1))
sys.path.insert(0, str(ROOT))

from common.scorer import (  # noqa: E402
    Scorer,
    normalize_score,
    prepare_report_text,
    build_source_excerpt,
    build_source_map,
)


def _mock_config():
    config = MagicMock()
    config.scoring_model = "test-model"
    config.get_client.return_value = MagicMock()
    config.max_retries = 1
    config.max_report_chars = 20000
    config.scoring_batch_size = 10
    config.scoring_temperature = 0.1
    return config


def _sample_task() -> dict:
    return {
        "task_type": "data_analysis",
        "rubrics": {
            "total_score": 7,
            "dimensions": [
                {
                    "dimension_id": "information_acquisition",
                    "dimension_name": "IA",
                    "max_score": 3,
                    "items": [
                        {
                            "rubric_id": "R1",
                            "role": "Critical",
                            "weight": 4,
                            "question": "Does the report define X?",
                            "source_ids": ["S1"],
                        },
                        {
                            "rubric_id": "R2",
                            "role": "Standard",
                            "weight": 1,
                            "question": "Does the report mention Y?",
                            "source_ids": [],
                        },
                    ],
                },
                {
                    "dimension_id": "scientific_reasoning",
                    "dimension_name": "SR",
                    "max_score": 4,
                    "items": [
                        {
                            "rubric_id": "R3",
                            "role": "Mandatory",
                            "weight": 2,
                            "question": "Does the report analyze Z?",
                            "source_ids": ["S1"],
                        },
                    ],
                },
            ],
        },
    }


class TestNormalizeScore(unittest.TestCase):
    def test_valid_scores(self):
        self.assertEqual(normalize_score(4, 4)[0], 4.0)
        self.assertEqual(normalize_score(2, 4)[0], 2.0)
        self.assertEqual(normalize_score(0, 4)[0], 0.0)

    def test_clamp_above_max(self):
        score, warns = normalize_score(99, 4)
        self.assertEqual(score, 4.0)
        self.assertTrue(any("clamped" in w for w in warns))

    def test_snap_to_nearest_tier(self):
        score, warns = normalize_score(1.7, 2)
        self.assertEqual(score, 2.0)
        self.assertTrue(any("snapped" in w for w in warns))

    def test_half_point_standard(self):
        score, _ = normalize_score(0.5, 1)
        self.assertEqual(score, 0.5)

    def test_invalid_type(self):
        score, warns = normalize_score("bad", 2)
        self.assertEqual(score, 0.0)
        self.assertIn("invalid_score_type", warns)


class TestPrepareReportText(unittest.TestCase):
    def test_short_report_unchanged(self):
        text = "Hello " * 100
        out, meta = prepare_report_text(text, max_chars=5000)
        self.assertEqual(out, text)
        self.assertFalse(meta["truncated"])

    def test_long_report_truncated(self):
        head = "A" * 15000
        tail = "B" * 15000
        body = head + "\n## Conclusion\nFinal verdict here.\n" + tail
        out, meta = prepare_report_text(body, max_chars=8000)
        self.assertTrue(meta["truncated"])
        self.assertLessEqual(len(out), 8500)
        self.assertIn("Conclusion", out)
        self.assertIn("BBBB", out)


class TestAggregateScores(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer(_mock_config())

    def test_aggregate_respects_weights(self):
        task = _sample_task()
        scored = [
            {"rubric_id": "R1", "score": 4, "reason": "ok"},
            {"rubric_id": "R2", "score": 1, "reason": "ok"},
            {"rubric_id": "R3", "score": 2, "reason": "ok"},
        ]
        result = self.scorer._aggregate_scores(
            scored, task, "/tmp/report.md", "/tmp/out", {"warnings": []}
        )
        self.assertEqual(result["raw_score"], 7.0)
        self.assertEqual(result["total_score"], 7)
        self.assertEqual(result["scoring_meta"]["full_mark_count"], 3)

    def test_missing_items_marked_not_scored(self):
        task = _sample_task()
        scored = [{"rubric_id": "R1", "score": 4, "reason": "ok"}]
        result = self.scorer._aggregate_scores(
            scored, task, "report.md", None, {"warnings": []}
        )
        r2 = next(it for it in result["items"] if it["rubric_id"] == "R2")
        self.assertEqual(r2["score"], 0)
        self.assertEqual(r2["reason"], "Not scored")


class TestBatchScoringMock(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer(_mock_config())

    @patch.object(Scorer, "_call_llm_json")
    def test_missing_batch_items_retried(self, mock_llm):
        def llm_side_effect(prompt, system=""):
            if "R2" in prompt and prompt.count("Rubric Items") == 0:
                return {"rubric_id": "R2", "score": 1, "reason": "b"}
            return [{"rubric_id": "R1", "score": 4, "reason": "a"}]

        mock_llm.side_effect = llm_side_effect
        batch = _sample_task()["rubrics"]["dimensions"][0]["items"]
        results, meta = self.scorer._score_batched(
            "report text", batch, {}, "", None
        )
        self.assertEqual(len(results), 2)
        self.assertIn("R2", meta["retried_items"])
        self.assertEqual(results[1]["score"], 1.0)

    @patch.object(Scorer, "_call_llm_json")
    def test_batch_failure_falls_back_to_single(self, mock_llm):
        mock_llm.side_effect = [
            ValueError("batch fail"),
            {"rubric_id": "R1", "score": 2, "reason": "partial"},
            {"rubric_id": "R2", "score": 0, "reason": "none"},
        ]
        batch = _sample_task()["rubrics"]["dimensions"][0]["items"]
        results = self.scorer._score_batch("report", batch, {}, "")
        self.assertEqual(len(results), 2)
        # binary 模式：LLM 给 2/4 视为「部分满足」→ 归并为 0 或满分（≥半权重→满分）
        self.assertEqual(results[0]["score"], 4.0)
        self.assertIn("binary_mode_no_half_credit", results[0].get("normalization_warnings", []))


class TestSourceContext(unittest.TestCase):
    def test_build_source_excerpt(self):
        doc = MagicMock()
        doc.file_name = "paper.pdf"
        doc.get_summary_for_llm.return_value = "Summary text"
        smap = {"S1": doc}
        excerpt = build_source_excerpt(smap, ["S1"])
        self.assertIn("S1", excerpt)
        self.assertIn("Summary text", excerpt)

    def test_empty_source_ids(self):
        self.assertEqual(build_source_excerpt({}, []), "")


class TestScorerIntegrationMock(unittest.TestCase):
    @patch.object(Scorer, "_call_llm_json")
    def test_end_to_end_score(self, mock_llm):
        mock_llm.return_value = [
            {"rubric_id": "R1", "score": 5, "reason": "over"},
            {"rubric_id": "R2", "score": 0.5, "reason": "half"},
        ]
        scorer = Scorer(_mock_config())

        report_path = ROOT / "样例/Deep交付模板/数据分析报告/self_check/report.md"
        if not report_path.exists():
            self.skipTest("sample report not found")

        task = _sample_task()
        task["rubrics"]["dimensions"] = [task["rubrics"]["dimensions"][0]]
        task["rubrics"]["dimensions"][0]["max_score"] = 5
        task["rubrics"]["total_score"] = 5

        result = scorer.score(str(report_path), task, output_dir=None)
        self.assertLessEqual(result["raw_score"], result["total_score"])
        self.assertIn("scoring_meta", result)
        self.assertEqual(result["items"][0]["score"], 4.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
