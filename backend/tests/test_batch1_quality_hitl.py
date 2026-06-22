"""Batch 1 — CQS / execution metadata / HITL gate 测试"""
import unittest

from app.core.execution_metadata import annotate_validation_execution_metadata
from app.core.quality_scoring import (
    enrich_quality_trend_entry,
    normalize_raw_to_cqs,
    summarize_cqs_trend,
)
from app.services.closed_loop_quality_service import compute_quality_acceptance
from app.services.stage_human_loop_service import StageHumanLoopService


class TestQualityScoring(unittest.TestCase):
    def test_normalize_ensemble_score(self):
        self.assertEqual(normalize_raw_to_cqs(8.0, "ensemble_review"), 80.0)

    def test_enrich_trend_entry(self):
        entry = enrich_quality_trend_entry(
            {"stage": "ensemble_review", "score": 7.5},
            "ensemble_review",
            {"decision": "Accept"},
        )
        self.assertGreaterEqual(entry["cqs"], 75.0)
        self.assertEqual(entry["score"], entry["cqs"])

    def test_cqs_trend_summary(self):
        trend = [
            enrich_quality_trend_entry({"stage": "a", "score": 6.0}),
            enrich_quality_trend_entry({"stage": "b", "score": 8.0}),
        ]
        summary = summarize_cqs_trend(trend)
        self.assertTrue(summary["cqs_improved"])
        self.assertGreater(summary["cqs_delta"], 0)


class TestExecutionMetadata(unittest.TestCase):
    def test_sandbox_tier(self):
        sv = annotate_validation_execution_metadata(
            {"sandbox_execution": {"success": True, "return_code": 0}},
            project_mode="general",
        )
        self.assertEqual(sv["execution_tier"], "real_sandbox")

    def test_federated_simulation(self):
        sv = annotate_validation_execution_metadata(
            {"federated_pilot": {"execution_mode": "simulation"}},
            project_mode="federated_learning",
        )
        self.assertEqual(sv["execution_tier"], "csv_simulation")


class TestClosedLoopQualityCQS(unittest.TestCase):
    def test_quality_acceptance_uses_cqs(self):
        trend = [
            enrich_quality_trend_entry({"stage": "discovery_r2", "score": 6.0}),
            enrich_quality_trend_entry({"stage": "discovery_r3", "score": 8.0}),
        ]
        qa = compute_quality_acceptance(quality_trend=trend)
        self.assertIsNotNone(qa.get("cqs_delta"))
        self.assertTrue(qa.get("cqs_improved"))


class TestHitlGateService(unittest.TestCase):
    def test_collect_feedback_empty_without_db(self):
        self.assertTrue(hasattr(StageHumanLoopService, "get_hitl_gate_status"))
        self.assertTrue(hasattr(StageHumanLoopService, "resume_hitl_gate"))


if __name__ == "__main__":
    unittest.main()
