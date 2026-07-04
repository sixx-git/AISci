"""研究问题字段 Pipeline 回填测试"""
from types import SimpleNamespace

from app.services.project_research_backfill_service import (
    backfill_from_data_acquisition,
    backfill_from_knowledge_gap,
    backfill_from_problem_understanding,
)


def _project(**kwargs):
    defaults = {
        "research_question": "",
        "research_domain": "",
        "research_goal": "",
        "research_background": "",
        "data_source": "",
        "constraints": "",
        "expected_output": "",
        "config": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_backfill_problem_understanding_fills_empty_fields():
    project = _project(research_question="短问题")
    pu = {
        "problem_statement": "如何在 Non-IID 条件下提升联邦学习精度？",
        "research_domain": "联邦学习",
        "scope_boundary": "聚焦 Non-IID 客户端与通信效率",
        "constraints": ["通信带宽有限", "隐私预算约束"],
        "expected_output": ["baseline 对比", "通信-精度分析"],
    }
    updates = backfill_from_problem_understanding(project, pu)
    assert updates["research_domain"] == "联邦学习"
    assert updates["research_goal"] == "聚焦 Non-IID 客户端与通信效率"
    assert "通信带宽有限" in updates["constraints"]
    assert "baseline 对比" in updates["expected_output"]
    assert "Non-IID" in updates["research_question"]


def test_backfill_problem_understanding_does_not_override_existing():
    project = _project(
        research_domain="用户指定领域",
        research_goal="用户目标",
        constraints="已有约束",
    )
    pu = {
        "research_domain": "AI 推断领域",
        "scope_boundary": "推断范围",
        "constraints": ["新约束"],
    }
    updates = backfill_from_problem_understanding(project, pu)
    assert updates == {}


def test_backfill_knowledge_gap_fills_background():
    project = _project()
    kg = {
        "knowledge_gaps": [
            {"description": "缺乏 Non-IID baseline 对比"},
            {"description": "通信开销量化不足"},
        ]
    }
    updates = backfill_from_knowledge_gap(project, kg)
    assert "Non-IID baseline" in updates["research_background"]
    assert "通信开销" in updates["research_background"]


def test_backfill_data_acquisition_fills_source_and_hints():
    project = _project()
    da = {
        "search_summary": {
            "merged": {"csv_path": "/data/merged.csv", "merge_strategy": "join"},
            "external_candidates": [
                {"dataset_name": "FL Benchmark", "source_platform": "huggingface"},
            ],
            "data_spec": {
                "entities_of_interest": ["client_id"],
                "target_variables": ["accuracy", "f1_score"],
                "dataset_keywords": ["federated", "non-iid"],
            },
        }
    }
    fields, config = backfill_from_data_acquisition(project, da)
    assert "merged.csv" in fields["data_source"]
    assert "FL Benchmark" in fields["data_source"]
    hints = config["data_spec_hints"]
    assert "client_id" in hints["entities_of_interest"]
    assert "accuracy" in hints["target_variables"]
    assert "huggingface" in hints["preferred_sources"]
    assert hints["merge_strategy_hint"] == "join"
