"""部分轮次 / 失败反例应可写入报告 small_validation。"""
from __future__ import annotations

from app.agents.report_generation_agent import ReportGenerationAgent
from app.services.iterative_experiment_service import IterativeExperimentService


def _partial_experiment() -> dict:
    return {
        "id": "exp-partial",
        "phase": "running",
        "current_iteration": 3,
        "max_iterations": 10,
        "hypothesis": "H1",
        "data_config": {"source_path": "demo.csv", "source_type": "local", "columns": ["a", "b"]},
        "initial_plan": {"methodology": "m", "description": "d", "success_criteria": ["acc>0.8"]},
        "iterations": [
            {
                "iteration_number": 1,
                "status": "success",
                "metrics": {"accuracy": 0.72, "primary_metric": 0.72},
                "result": {
                    "metrics": {"accuracy": 0.72},
                    "charts": [{"name": "acc.png", "path": "acc.png", "note": "acc"}],
                    "summary": "第一轮可用",
                },
                "analysis": {"summary": "尚可", "findings": ["趋势正向"]},
            },
            {
                "iteration_number": 2,
                "status": "failed",
                "error_message": "KeyError: label column missing",
                "metrics": {},
                "result": {"metrics": {}, "charts": [], "summary": "脚本崩溃"},
                "analysis": {
                    "summary": "特征与标签不对齐",
                    "identified_issues": ["缺少标签列"],
                    "weaknesses": ["当前管线无法验证假设"],
                },
            },
            {
                "iteration_number": 3,
                "status": "partial",
                "metrics": {"f1": 0.55},
                "result": {"metrics": {"f1": 0.55}, "charts": [], "summary": "部分指标"},
                "analysis": {"summary": "未达阈值"},
            },
        ],
    }


def test_resolve_includes_failed_and_partial_rounds():
    metrics, plots, evidence = IterativeExperimentService._resolve_iteration_evidence(
        _partial_experiment()
    )
    assert metrics.get("accuracy") == 0.72
    assert metrics.get("f1") == 0.55
    assert evidence["has_negative_evidence"] is True
    assert len(evidence["failed_rounds"]) == 1
    assert evidence["failed_rounds"][0]["error_message"]
    assert evidence["progress"]["completed_full_plan"] is False
    # 图表路径可能不存在于磁盘，但仍应尝试收录条目
    assert isinstance(plots, list)


def test_synthesize_marks_partial_and_counterexamples():
    synth = IterativeExperimentService.synthesize_report_fields(_partial_experiment())
    sv = synth["small_validation"]
    assert sv["validation_status"] == "partial"
    assert sv["results"]["result_type_summary"] == "has_actual_results"
    actual = sv["results"]["actual_results"]
    assert actual["failed_iterations"]
    assert actual["sandbox_execution"]["partial_run"] is True
    assert "反例" in (actual.get("summary") or "") or actual["failed_iterations"]


def test_enrich_writes_counterexamples_section():
    synth = IterativeExperimentService.synthesize_report_fields(_partial_experiment())
    sv = synth["small_validation"]
    out = ReportGenerationAgent()._enrich_results_with_categorized(
        {"chapters": {"results": ""}},
        sv,
        None,
    )
    text = out["chapters"]["results"]
    assert "Actual Results" in text
    assert "阶段性结果" in text
    assert "Counterexamples" in text or "反例" in text
    assert "KeyError" in text or "缺少标签" in text


def test_enrich_writes_discussion_section():
    synth = IterativeExperimentService.synthesize_report_fields(_partial_experiment())
    sv = synth["small_validation"]
    out = ReportGenerationAgent()._enrich_results_with_categorized(
        {"chapters": {"results": "仅有预期结果占位文字" * 3}},
        sv,
        None,
    )
    text = out["chapters"]["results"]
    assert "结果分析与讨论" in text
    assert "主要发现" in text
    assert "与科学假设的对照" in text
    assert "局限与后续" in text
    assert out["results"].get("discussion")


def test_enrich_failure_only_still_writes_section():
    exp = {
        "id": "exp-fail",
        "phase": "running",
        "current_iteration": 1,
        "max_iterations": 10,
        "hypothesis": "H2",
        "data_config": {"source_path": "x.csv"},
        "initial_plan": {},
        "iterations": [
            {
                "iteration_number": 1,
                "status": "failed",
                "error_message": "timeout in training",
                "result": {"summary": "训练超时"},
                "analysis": {
                    "identified_issues": ["方法在当前数据上无法收敛"],
                    "weaknesses": ["假设难以用该方法验证"],
                },
            }
        ],
    }
    sv = IterativeExperimentService.synthesize_report_fields(exp)["small_validation"]
    assert sv["results"]["result_type_summary"] == "has_negative_evidence"
    out = ReportGenerationAgent()._enrich_results_with_categorized(
        {"chapters": {"results": ""}},
        sv,
        None,
    )
    text = out["chapters"]["results"]
    assert "反例" in text or "Counterexamples" in text
    assert "timeout" in text or "无法" in text
