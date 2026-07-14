"""Phase C — 3D Pareto 测试"""
import unittest

from app.core.iterative_science import compute_pareto_frontier_3d


class TestPhaseC(unittest.TestCase):
    def test_pareto_3d(self):
        comp = [
            {"method": "A", "global_accuracy": 0.9, "communication_cost_mb": 200, "privacy_leakage_risk": 0.3},
            {"method": "B", "global_accuracy": 0.85, "communication_cost_mb": 80, "privacy_leakage_risk": 0.15},
        ]
        pf3 = compute_pareto_frontier_3d(comp)
        self.assertEqual(len(pf3["points"]), 2)
        self.assertGreaterEqual(len(pf3["frontier_3d"]), 1)


if __name__ == "__main__":
    unittest.main()
