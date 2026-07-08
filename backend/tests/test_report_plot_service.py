"""报告图表服务回归测试。"""
from __future__ import annotations

from app.services.report_plot_service import (
    dedupe_report_plots,
    is_sandbox_metrics_placeholder,
    is_sandbox_output_complete,
    slim_plot_for_db,
)


def test_is_sandbox_metrics_placeholder():
    assert is_sandbox_metrics_placeholder({}) is True
    assert is_sandbox_metrics_placeholder({"note": "no metrics emitted"}) is True
    assert is_sandbox_metrics_placeholder({"primary_metric": 0.91}) is False


def test_is_sandbox_output_complete_with_plots():
    assert is_sandbox_output_complete({"note": "no metrics emitted"}, [{"plot_id": "a"}]) is True


def test_dedupe_report_plots_prefers_sandbox():
    plots = [
        {"plot_id": "a", "title": "EDA", "chart_kind": "descriptive_stat"},
        {"plot_id": "a", "title": "Pilot", "source": "pilot_analysis", "chart_kind": "experiment_result"},
    ]
    out = dedupe_report_plots(plots)
    assert len(out) == 1
    assert out[0]["source"] == "pilot_analysis"


def test_slim_plot_for_db_strips_base64():
    slim = slim_plot_for_db({
        "plot_id": "x",
        "title": "t",
        "base64": "abc",
        "url": "/storage/charts/x.png",
    })
    assert "base64" not in slim
    assert slim["url"] == "/storage/charts/x.png"
