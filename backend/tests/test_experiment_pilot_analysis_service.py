"""experiment_pilot_analysis_service 单元测试。"""
import tempfile
import unittest

from app.services.experiment_pilot_analysis_service import run_pilot_from_csv


class TestExperimentPilotAnalysisService(unittest.TestCase):
    def test_pilot_with_slice_index_split(self):
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = f"{tmp}/sample.csv"
            pd.DataFrame({
                "slice_index": list(range(40)),
                "mean": [0.1 + i * 0.01 for i in range(40)],
                "spatial_x": [0.0] * 40,
            }).to_csv(csv_path, index=False)

            ed = {"baselines": "Baseline A; Proposed B", "metrics": "RMSE"}
            result = run_pilot_from_csv(csv_path, ed, output_dir=tmp)
            self.assertTrue(result["success"])
            self.assertIn("Baseline A", result["metrics"])
            self.assertGreaterEqual(len(result["plots"]), 1)
            cmp_text = result["plots"][0].get("baseline_comparison") or ""
            self.assertIn("±", cmp_text)
            self.assertIn("Δ=", cmp_text)


if __name__ == "__main__":
    unittest.main()
