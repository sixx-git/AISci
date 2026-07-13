"""DatasetSemanticUnderstandingSkill 回归测试。"""
from __future__ import annotations

from unittest.mock import patch

from app.skills.data.dataset_semantic_understanding_skill import (
    DatasetSemanticUnderstandingSkill,
    merge_semantic_into_metadata,
    normalize_semantic_schema,
    rule_fallback_semantic_schema,
)


def test_rule_fallback_detects_score_columns():
    columns = ["Indicator ID", "Score Rater A", "Motivation Rater A", "Final Score"]
    payload = rule_fallback_semantic_schema(columns=columns, dtypes={"Final Score": "BIGINT"})
    assert "Final Score" in payload["recommended_targets"]
    assert payload["column_roles"]["Indicator ID"] == "entity_key"
    assert payload["column_roles"]["Motivation Rater A"] == "text_metadata"
    assert "regression" in payload["target_candidates"]


def test_normalize_semantic_schema_filters_unknown_columns():
    raw = {
        "column_roles": {"real_col": "target_regression", "fake_col": "ignore"},
        "recommended_targets": ["real_col", "ghost"],
        "join_keys": ["real_col"],
        "feature_columns": ["other"],
        "quality_issues": ["ok"],
        "experiment_hints": "hint",
        "target_candidates": {"regression": ["real_col"]},
        "numeric_field_candidates": ["real_col"],
        "categorical_field_candidates": [],
    }
    out = normalize_semantic_schema(raw, columns=["real_col", "other"])
    assert "fake_col" not in out["column_roles"]
    assert out["recommended_targets"] == ["real_col"]
    assert "ghost" not in out["recommended_targets"]
    assert out["join_keys"] == ["real_col"]


def test_merge_semantic_into_metadata():
    merged = merge_semantic_into_metadata(
        {"large_file_probe": True},
        rule_fallback_semantic_schema(columns=["y", "x"], dtypes={"y": "float"}),
    )
    assert "semantic_schema" in merged
    assert merged["semantic_schema"]["source"] == "rule_fallback"
    assert "target_candidates" in merged


async def _run_skill(input_data, context=None):
    skill = DatasetSemanticUnderstandingSkill()
    return await skill.run(input_data=input_data, context=context or {})


def test_skill_rule_fallback_when_no_api_key():
    import asyncio

    input_data = {
        "filename": "test.csv",
        "columns": ["id", "accuracy"],
        "dtypes": {"accuracy": "float"},
        "n_rows": 10,
        "n_columns": 2,
        "preview": [{"id": 1, "accuracy": 0.9}],
        "statistics": {},
    }
    with patch("app.skills.data.dataset_semantic_understanding_skill.settings") as mock_settings:
        mock_settings.USE_MOCK_LLM = True
        mock_settings.QWEN_API_KEY = ""
        result = asyncio.run(_run_skill(input_data))
    assert result.success
    assert result.data.get("source") == "rule_fallback"
    assert "accuracy" in result.data.get("recommended_targets", [])


def test_skill_uses_llm_when_available():
    import asyncio

    llm_payload = {
        "column_roles": {"id": "entity_key", "accuracy": "target_regression"},
        "recommended_targets": ["accuracy"],
        "join_keys": ["id"],
        "feature_columns": [],
        "quality_issues": [],
        "experiment_hints": "分类准确率分析",
        "parsing_notes": "",
        "target_candidates": {"regression": ["accuracy"]},
        "numeric_field_candidates": ["accuracy"],
        "categorical_field_candidates": [],
        "generic_metric_candidates": ["accuracy"],
    }
    with patch("app.skills.data.dataset_semantic_understanding_skill.settings") as mock_settings:
        mock_settings.USE_MOCK_LLM = False
        mock_settings.QWEN_API_KEY = "test-key"
        with patch(
            "app.services.qwen_client.qwen_structured_chat",
            return_value=llm_payload,
        ):
            result = asyncio.run(_run_skill({
                "filename": "metrics.csv",
                "columns": ["id", "accuracy"],
                "dtypes": {"accuracy": "float"},
                "n_rows": 100,
                "n_columns": 2,
                "preview": [],
                "statistics": {},
                "research_question": "比较联邦学习准确率",
            }))
    assert result.success
    assert result.data.get("source") == "llm"
    assert result.data["experiment_hints"] == "分类准确率分析"
