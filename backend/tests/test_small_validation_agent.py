"""小样验证 Agent 空值防护测试。"""
from app.agents.small_validation_agent import (
    SmallValidationAgent,
    _preliminary_analysis_data,
    _skill_block,
)


def test_skill_block_handles_none_values():
    assert _skill_block({"preliminary_analysis": None}, "preliminary_analysis") == {}
    assert _skill_block(None, "preliminary_analysis") == {}


def test_preliminary_analysis_data_when_data_is_none():
    skill_outputs = {
        "preliminary_analysis": {
            "success": True,
            "data": None,
            "warnings": [],
        }
    }
    assert _preliminary_analysis_data(skill_outputs) == {}


def test_build_categorized_results_with_null_preliminary_data():
    agent = SmallValidationAgent()
    result = agent._build_categorized_results(
        {"has_real_data": 0},
        {
            "preliminary_analysis": {
                "success": True,
                "data": None,
                "warnings": ["warn"],
            }
        },
        hypothesis="H1",
        experiment_design={"metrics": "AUC", "expected_outcome": "improve"},
        modeling_results=None,
    )
    assert result["result_type_summary"] in ("none", "expected_only", "has_actual_results")
    assert "expected_results" in result
