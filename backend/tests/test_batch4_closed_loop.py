"""Batch 4 — Decision Log / Executability / Iteration Control / Gap Search"""
import os
import tempfile
import unittest

from app.core.closed_loop_decisions import (
    append_closed_loop_decision,
    build_iteration_causal_summary,
    infer_driven_by,
)
from app.core.iteration_control import evaluate_discovery_continuation
from app.core.plan_executability import assess_plan_executability
from app.services.data_finder_gap_search import (
    build_gap_search_queries,
    pick_import_candidates,
    should_run_gap_enrichment,
)


class TestBatch4DecisionLog(unittest.TestCase):
    def test_append_decision(self):
        decisions = []
        entry = append_closed_loop_decision(
            decisions,
            trigger="ensemble_not_accept",
            action="discovery_refine",
            reason="score too low",
            round_num=2,
        )
        self.assertEqual(entry["trigger"], "ensemble_not_accept")
        self.assertEqual(len(decisions), 1)

    def test_causal_summary(self):
        before = {"supporting_fact_count": 2, "experimental_steps_preview": "step A"}
        after = {"supporting_fact_count": 5, "experimental_steps_preview": "step B"}
        summary = build_iteration_causal_summary(
            before,
            after,
            rollback_meta={"literature_refresh": {"data_finder_rerun": True, "new_facts": 3}},
            data_finder_before={"merged": {"row_count": 10}},
            data_finder_after={"merged": {"row_count": 25}, "coverage_report": {"completeness_score": 72}},
        )
        self.assertTrue(summary["data_changes"])
        self.assertTrue(summary["plan_changes"])
        self.assertIn("data_finder", summary["driven_by"])

    def test_infer_driven_by(self):
        self.assertEqual(
            infer_driven_by({"literature_refresh": {"new_facts": 2}}, ["weak evidence"]),
            "literature_refresh",
        )


class TestBatch4IterationControl(unittest.TestCase):
    def test_stop_stagnant(self):
        trend = [
            {"stage": "r1", "cqs": 60},
            {"stage": "r2", "cqs": 61},
            {"stage": "r3", "cqs": 61.5},
        ]
        result = evaluate_discovery_continuation(trend, round_num=4, min_improvement_delta=3.0)
        self.assertEqual(result["action"], "stop_stagnant")

    def test_continue_when_improved(self):
        trend = [{"cqs": 55}, {"cqs": 62}]
        result = evaluate_discovery_continuation(trend, round_num=2)
        self.assertEqual(result["action"], "continue")


class TestBatch4Executability(unittest.TestCase):
    def test_executability_with_columns(self):
        gate = assess_plan_executability(
            {
                "experimental_steps": "Train model on accuracy metric",
                "metrics": "global_accuracy, f1_score",
                "verifiable_hypothesis": {"primary_metric": "global_accuracy"},
            },
            data_context={
                "datasets": [{"columns": ["global_accuracy", "client_id", "method"]}],
            },
        )
        self.assertGreater(gate["score"], 60)
        self.assertTrue(gate["passed"])

    def test_executability_missing_data(self):
        gate = assess_plan_executability(
            {"experimental_steps": "", "metrics": ""},
            data_context={},
        )
        self.assertFalse(gate["passed"])


class TestBatch4GapSearch(unittest.TestCase):
    def test_gap_queries_from_coverage(self):
        queries = build_gap_search_queries(
            {"gaps": ["未命中外部开放数据库候选"], "completeness_score": 50},
            ["improve federated accuracy data"],
            {"dataset_keywords": ["federated learning benchmark"]},
        )
        self.assertTrue(queries)
        self.assertTrue(should_run_gap_enrichment({"completeness_score": 50}))

    def test_pick_hf_candidates(self):
        picks = pick_import_candidates([
            {"source_platform": "OpenAlex", "confidence": 0.5},
            {"source_platform": "HuggingFace Datasets", "dataset_name": "org/ds", "confidence": 0.6},
        ], max_count=1)
        self.assertEqual(len(picks), 1)
        self.assertIn("HuggingFace", picks[0]["source_platform"])


if __name__ == "__main__":
    unittest.main()
