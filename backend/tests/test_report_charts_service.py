"""report_charts_service 单元测试。"""
import unittest

from app.services.report_charts_service import (
    _extract_method_metric_comparisons,
    _infer_baseline_comparison,
    build_experiment_plot_specs,
    build_figure_caption,
)


class TestReportChartsService(unittest.TestCase):
    def test_build_figure_caption(self):
        caption = build_figure_caption(
            experiment_condition="N-body 模拟，含潮汐耗散",
            metric="Lyapunov 指数 (1/Myr)",
            metric_direction="lower_is_better",
            baseline_comparison="本文方法相对二体基线降低 40%",
            dataset="JWST NIRSpec 切片",
        )
        self.assertIn("实验条件", caption)
        self.assertIn("越低越好", caption)
        self.assertIn("对比结论", caption)

    def test_extract_nested_method_metrics(self):
        metrics = {
            "baseline": {"rmse": 0.12, "rmse_std": 0.01},
            "ours": {"rmse": 0.08, "rmse_std": 0.008},
        }
        comps = _extract_method_metric_comparisons(metrics)
        self.assertGreaterEqual(len(comps), 1)
        self.assertEqual(comps[0]["metric"], "rmse")
        self.assertEqual(len(comps[0]["series"]), 2)

    def test_build_experiment_plot_specs_from_context(self):
        ctx = {
            "experiment_design": {
                "methods": "N-body + 潮汐耗散",
                "datasets": "模拟行星系统",
                "baselines": ["经典二体"],
                "metrics": ["RMSE", "Lyapunov"],
            },
            "small_validation": {
                "sandbox_execution": {
                    "metrics": {
                        "baseline": {"rmse": 0.15, "rmse_std": 0.02},
                        "ours": {"rmse": 0.09, "rmse_std": 0.01},
                    }
                },
            },
            "datasets": "模拟行星系统",
            "baselines": ["经典二体"],
            "metrics": ["RMSE"],
            "methods": "N-body + 潮汐耗散",
        }
        specs = build_experiment_plot_specs(ctx)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["type"], "grouped_bar")
        self.assertIn("caption", specs[0])
        self.assertIn("experiment_condition", specs[0])
        self.assertTrue(specs[0]["has_legend"])

    def test_infer_baseline_comparison_quantitative(self):
        series = [
            {"name": "baseline", "values": [{"x": "rmse", "y": 0.12, "err": 0.01}]},
            {"name": "ours", "values": [{"x": "rmse", "y": 0.08, "err": 0.008}]},
        ]
        text = _infer_baseline_comparison(series, "rmse")
        self.assertIn("0.0800", text)
        self.assertIn("Δ=", text)
        self.assertIn("降低", text)


if __name__ == "__main__":
    unittest.main()
