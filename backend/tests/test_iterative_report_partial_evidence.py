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


def test_synthesize_includes_narrative_brief():
    synth = IterativeExperimentService.synthesize_report_fields(_partial_experiment())
    sv = synth["small_validation"]
    brief = sv.get("narrative_brief") or {}
    assert brief.get("evidence_verdict") in {
        "supported", "inconclusive", "contradicted", "blocked"
    }
    assert isinstance(brief.get("iteration_timeline"), list)
    assert len(brief["iteration_timeline"]) >= 2
    assert brief["evidence_verdict"] == "inconclusive"  # 有正有负 + partial


def test_iteration_narrative_skill_story_arc():
    from app.skills.report.iteration_narrative_skill import IterationNarrativeSkill

    synth = IterativeExperimentService.synthesize_report_fields(_partial_experiment())
    narr = IterationNarrativeSkill.build_narrative(small_validation=synth["small_validation"])
    assert narr.get("story_arc")
    assert narr.get("evidence_verdict") == "inconclusive"
    assert narr.get("negative_or_partial_results_paragraph")
    para = narr["negative_or_partial_results_paragraph"]
    assert "成功验证" not in para and "显著提升" not in para
    assert "阶段性" in para or "外推" in para or "试探" in para


def test_enrich_includes_iteration_story():
    synth = IterativeExperimentService.synthesize_report_fields(_partial_experiment())
    sv = synth["small_validation"]
    out = ReportGenerationAgent()._enrich_results_with_categorized(
        {"chapters": {"results": ""}},
        sv,
        None,
    )
    text = out["chapters"]["results"]
    assert "迭代演化叙事" in text or "第1轮" in text
    assert "结果分析与讨论" in text


def test_align_abstract_uses_verdict():
    from app.services.report_content_sanitizer import align_paper_abstract

    sv = {
        "narrative_brief": {"evidence_verdict": "contradicted", "progress": {}},
        "results": {
            "result_type_summary": "has_negative_evidence",
            "actual_results": {"failed_iterations": [{"iteration_number": 1}]},
        },
        "sandbox_execution": {"metrics": {}, "partial_run": True},
    }
    text = align_paper_abstract("本研究成功验证了假设并显著提升准确率。", sv)
    assert "成功验证" not in text
    assert "未能稳定" in text or "尚待" in text or "方法边界" in text


def test_enrich_no_evidence_omits_actual_results_heading():
    out = ReportGenerationAgent()._enrich_results_with_categorized(
        {
            "chapters": {
                "results": (
                    "### Actual Results（实际分析结果）\n\n"
                    "### Expected Results（预期结果）\n\n"
                    "预期通过模拟得到后验约束。"
                )
            }
        },
        {"results": {"expected_results": {"note": "only expected"}}},
        None,
    )
    text = out["chapters"]["results"]
    assert "Actual Results" not in text
    assert "Expected Results" in text


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
