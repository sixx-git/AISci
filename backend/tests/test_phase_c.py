"""Phase C — 联邦 runtime / Discovery 双门槛 / 3D Pareto 测试"""
import os
import tempfile
import unittest

import pandas as pd

from app.core.iterative_science import (
    compute_pareto_frontier_3d,
    evaluate_discovery_federated_acceptance,
)
from app.skills.federated_experiment._federated_runtime import run_federated_runtime_pilot


class TestPhaseC(unittest.TestCase):
    def test_runtime_horizontal_pilot(self):
        df = pd.DataFrame([
            {"client_id": "c1", "feature_a": 1.0, "feature_b": 0.2, "label": 1},
            {"client_id": "c1", "feature_a": 1.1, "feature_b": 0.3, "label": 0},
            {"client_id": "c2", "feature_a": 0.5, "feature_b": 0.8, "label": 1},
            {"client_id": "c2", "feature_a": 0.4, "feature_b": 0.9, "label": 0},
            {"client_id": "c3", "feature_a": 2.0, "feature_b": 0.1, "label": 1},
            {"client_id": "c3", "feature_a": 2.1, "feature_b": 0.0, "label": 0},
        ] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fl.csv")
            df.to_csv(path, index=False)
            pilot = run_federated_runtime_pilot(
                path,
                {"fl_setting": "horizontal_fl"},
                {"baselines": ["FedAvg"]},
            )
        self.assertIsNotNone(pilot)
        self.assertIn(pilot["execution_mode"], ("runtime_local", "flower"))
        self.assertGreater(len(pilot["metric_comparison"]), 0)

    def test_runtime_vfl_pilot(self):
        rows = []
        for i in range(20):
            rows.append({
                "party_id": "bank_a" if i % 2 == 0 else "bank_b",
                "entity_id": f"e{i:03d}",
                "feature_x": 0.2 + (i % 5) * 0.1,
                "feature_y": float(i % 3),
                "feature_owner": "bank_a" if i % 2 == 0 else "bank_b",
                "label_owner": "hosp",
                "label": i % 2,
            })
        df = pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vfl.csv")
            df.to_csv(path, index=False)
            pilot = run_federated_runtime_pilot(
                path,
                {"fl_setting": "vertical_fl"},
                {"baselines": ["SplitNN"]},
            )
        self.assertIsNotNone(pilot)
        self.assertEqual(pilot["execution_mode"], "fate_compatible")

    def test_pareto_3d(self):
        comp = [
            {"method": "A", "global_accuracy": 0.9, "communication_cost_mb": 200, "privacy_leakage_risk": 0.3},
            {"method": "B", "global_accuracy": 0.85, "communication_cost_mb": 80, "privacy_leakage_risk": 0.15},
        ]
        pf3 = compute_pareto_frontier_3d(comp)
        self.assertEqual(len(pf3["points"]), 2)
        self.assertGreaterEqual(len(pf3["frontier_3d"]), 1)

    def test_discovery_federated_acceptance(self):
        ok = evaluate_discovery_federated_acceptance(
            {
                "ensemble_decision": "Accept",
                "ensemble_overall": 8.0,
            },
            {
                "federated_pilot": {
                    "execution_mode": "runtime_local",
                    "best_method": "FedAvg-runtime",
                    "alignment_gate": {"passed": True, "skipped": True},
                }
            },
        )
        self.assertTrue(ok["accepted"])

        blocked = evaluate_discovery_federated_acceptance(
            {"ensemble_decision": "Accept", "ensemble_overall": 8.0},
            {"federated_pilot": {"execution_mode": "gate_blocked", "alignment_gate": {"passed": False}}},
        )
        self.assertFalse(blocked["accepted"])
        self.assertIn("gate", blocked["blockers"][0].lower())


if __name__ == "__main__":
    unittest.main()
