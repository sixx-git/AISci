"""Batch 2 — 通用 verifiable spec / 证据溯源 / 验证对照"""
import unittest

from app.core.iterative_science import (
    assess_evidence_sufficiency,
    attach_verifiable_specs_to_hypotheses,
    build_general_verifiable_hypothesis_spec,
    build_verifiable_hypothesis_spec_for_mode,
    compute_evidence_provenance_summary,
    evaluate_verifiable_spec_against_validation,
)


class TestBatch2VerifiableSpec(unittest.TestCase):
    def test_general_spec(self):
        spec = build_general_verifiable_hypothesis_spec(
            "X improves Y",
            {
                "validation_target": "F1",
                "expected_measurable_effect": "F1 +5%",
                "supporting_fact_ids": ["fact_001", "fact_002"],
                "evidence_level": "medium",
            },
        )
        self.assertEqual(spec["primary_metric"], "F1")
        self.assertIn("F1 +5%", spec["success_criteria"][0])
        self.assertEqual(spec["mode"], "general")

    def test_attach_specs(self):
        hg = attach_verifiable_specs_to_hypotheses(
            {
                "hypotheses": [
                    {
                        "hypothesis": "H1",
                        "supporting_fact_ids": ["f1"],
                        "validation_target": "Accuracy",
                    }
                ]
            },
            project_mode="general",
        )
        self.assertIn("verifiable_spec", hg["hypotheses"][0])
        self.assertIn("primary_verifiable_spec", hg)

    def test_federated_mode_routes(self):
        spec = build_verifiable_hypothesis_spec_for_mode(
            "FL hypo",
            project_mode="federated_learning",
            plan={"baselines": ["FedAvg"], "metrics": ["global_accuracy"]},
            fl_context={"fl_setting": "horizontal_fl"},
        )
        self.assertEqual(spec.get("fl_setting"), "horizontal_fl")
        self.assertEqual(spec.get("mode"), "federated_learning")
        self.assertIn("FedAvg", str(spec.get("comparison_baselines") or []))

    def test_evaluate_validation_sandbox(self):
        spec = build_general_verifiable_hypothesis_spec("H", {"supporting_fact_ids": ["f1"]})
        checks = evaluate_verifiable_spec_against_validation(
            {"sandbox_execution": {"success": True, "metrics": {"f1": 0.9}}},
            spec,
        )
        self.assertTrue(any(c["check_id"] == "sandbox_success" and c["passed"] for c in checks))

    def test_evidence_provenance(self):
        summary = compute_evidence_provenance_summary(
            {"supporting_fact_ids": ["a", "b"], "evidence_level": "high"}
        )
        self.assertEqual(summary["supporting_fact_count"], 2)

    def test_assess_sufficiency(self):
        weak = assess_evidence_sufficiency({"supporting_fact_ids": [], "evidence_level": "low"})
        self.assertEqual(weak["evidence_sufficiency"], "missing")
        ok = assess_evidence_sufficiency(
            {"supporting_fact_ids": ["f1", "f2", "f3"], "evidence_level": "high"}
        )
        self.assertEqual(ok["evidence_sufficiency"], "adequate")


if __name__ == "__main__":
    unittest.main()
