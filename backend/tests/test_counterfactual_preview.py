"""反事实预演（Counterfactual Preview）单元测试"""
import asyncio
from unittest.mock import MagicMock, patch

from app.core.pipeline_modes import resolve_run_options
from app.skills.counterfactual.counterfactual_preview_skill import (
    CounterfactualPreviewSkill,
    build_counterfactual_feedback_constraints,
    filter_falsify_scenarios,
)


def test_resolve_run_options_counterfactual_default_off():
    opts = resolve_run_options({})
    assert opts.get("enable_counterfactual_preview") is False


def test_resolve_run_options_counterfactual_can_disable():
    opts = resolve_run_options({"enable_counterfactual_preview": False})
    assert opts.get("enable_counterfactual_preview") is False


def test_resolve_run_options_literature_max_papers():
    opts = resolve_run_options({"literature_max_papers": 20})
    assert opts.get("literature_max_papers") == 20
    clamped = resolve_run_options({"literature_max_papers": 99})
    assert clamped.get("literature_max_papers") == 30


def test_filter_falsify_keeps_valid_scenario():
    valid_ids = {"fact_a", "fact_b"}
    scenarios = [
        {
            "scenario_id": "cf_1",
            "intervention": "移除联邦聚合中的 label skew 校正",
            "question": "若不做 skew 校正，全局模型是否仍优于 local only？",
            "predicted_outcome": "全局精度显著下降，local 模型在偏斜客户端上更稳",
            "failure_risk": "high",
            "confidence": "medium",
            "evidence_fact_ids": ["fact_a"],
            "cheap_test": "在 2 个偏斜客户端上对比 FedAvg vs local only",
            "decision_impact": "决定是否必须加入 skew-aware 聚合",
            "falsifiable": True,
        },
        {
            "intervention": "无干预",
            "question": "模糊问题？",
            "predicted_outcome": "也许",
            "failure_risk": "low",
            "confidence": "low",
            "evidence_fact_ids": [],
            "cheap_test": "",
            "falsifiable": True,
        },
    ]
    kept = filter_falsify_scenarios(
        scenarios,
        valid_fact_ids=valid_ids,
        hypothesis_text="label skew 联邦学习聚合",
    )
    assert len(kept) == 1
    assert kept[0]["scenario_id"] == "cf_1"


def test_filter_falsify_rejects_unknown_fact_ids():
    kept = filter_falsify_scenarios(
        [{
            "intervention": "改变学习率",
            "question": "若 lr 过大？",
            "predicted_outcome": "不收敛",
            "evidence_fact_ids": ["fact_unknown"],
            "cheap_test": "网格搜索 lr",
            "decision_impact": "选择 lr 范围",
            "falsifiable": True,
        }],
        valid_fact_ids={"fact_a"},
        hypothesis_text="学习率",
    )
    assert kept == []


def test_build_counterfactual_feedback_constraints():
    preview = {
        "summary": "主路径对 skew 敏感",
        "failure_predictions": ["聚合权重未对齐客户端分布"],
        "scenarios": [{
            "scenario_id": "cf_1",
            "failure_risk": "high",
            "question": "无 skew 校正？",
            "cheap_test": "对比 FedAvg baseline",
        }],
        "recommended_pivots": ["改用 skew-aware 聚合"],
        "proceed_to_experiment_design": False,
    }
    constraints = build_counterfactual_feedback_constraints(preview)
    assert any("反事实预演摘要" in c for c in constraints)
    assert any("失败模式" in c for c in constraints)
    assert any("高风险反事实" in c for c in constraints)
    assert any("转向建议" in c for c in constraints)
    assert any("对照组" in c for c in constraints)


def test_build_counterfactual_feedback_skipped():
    assert build_counterfactual_feedback_constraints({"skipped": True}) == []
    assert build_counterfactual_feedback_constraints(None) == []


def test_counterfactual_preview_skill_skips_without_reviews():
    skill = CounterfactualPreviewSkill()
    result = asyncio.run(skill.run({"hypothesis_review": {}}, {}))
    assert result.success
    assert result.data.get("skipped") is True


def test_counterfactual_preview_skill_llm_failure_non_blocking():
    skill = CounterfactualPreviewSkill()
    hr = {
        "primary_index": 0,
        "reviews": [{"hypothesis": "H1 about federated label skew", "rationale": "r"}],
    }
    with patch(
        "app.skills.counterfactual.counterfactual_preview_skill.qwen_structured_chat",
        side_effect=RuntimeError("mock llm down"),
    ):
        result = asyncio.run(
            skill.run(
                {"hypothesis_review": hr, "literature_facts": []},
                {"research_question": "RQ"},
            )
        )
    assert result.success
    assert result.data.get("skipped") is True
    assert result.data.get("reason") == "llm_error"


def test_pipeline_ensure_counterfactual_does_not_block_on_error():
    from app.services.pipeline_service import PipelineService

    svc = PipelineService(db=None)  # type: ignore[arg-type]
    svc._run_options = {"enable_counterfactual_preview": True}
    svc._stage_results = {}
    results = {
        "hypothesis_review": {
            "primary_index": 0,
            "reviews": [{"hypothesis": "test hypothesis federated", "rationale": "r"}],
        },
        "literature_mining": {"facts": []},
    }
    with patch.object(svc, "_exec_counterfactual_preview", side_effect=RuntimeError("boom")):
        svc._ensure_counterfactual_preview(results, "RQ")
    assert "counterfactual_preview" not in results


def test_pipeline_ensure_counterfactual_respects_flag():
    from app.services.pipeline_service import PipelineService

    svc = PipelineService(db=None)  # type: ignore[arg-type]
    svc._run_options = {"enable_counterfactual_preview": False}
    results = {
        "hypothesis_review": {
            "reviews": [{"hypothesis": "h", "rationale": "r"}],
        },
    }
    svc._ensure_counterfactual_preview(results, "RQ")
    assert "counterfactual_preview" not in results


def test_pipeline_ensure_counterfactual_stores_result():
    from app.services.pipeline_service import PipelineService

    svc = PipelineService(db=None)  # type: ignore[arg-type]
    svc._run_options = {"enable_counterfactual_preview": True}
    svc._stage_results = {}
    svc._record_closed_loop_event = MagicMock()
    preview = {
        "scenarios": [{"scenario_id": "cf_1"}],
        "summary": "ok",
        "proceed_to_experiment_design": True,
    }
    results = {
        "hypothesis_review": {
            "reviews": [{"hypothesis": "h", "rationale": "r"}],
        },
    }
    with patch.object(svc, "_exec_counterfactual_preview", return_value=preview):
        svc._ensure_counterfactual_preview(results, "RQ")
    assert results["counterfactual_preview"] == preview
    svc._record_closed_loop_event.assert_called_once()
