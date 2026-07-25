"""VariableDefinition.values：LLM 常输出描述字符串，须强制转为 list。"""
from schemas.experiment import ExperimentPlan, VariableDefinition, _coerce_variable_values


def test_coerce_range_in_parens_large():
    assert _coerce_variable_values("condition_idx (0-119)") == [0, 119]


def test_coerce_range_in_parens_small():
    assert _coerce_variable_values("movie_id (0-12)") == list(range(0, 13))


def test_coerce_bare_range():
    assert _coerce_variable_values("2-96") == [2, 96]


def test_coerce_json_list_string():
    assert _coerce_variable_values("[1, 2, 3]") == [1, 2, 3]


def test_coerce_comma_separated():
    assert _coerce_variable_values("A, B, C") == ["A", "B", "C"]


def test_variable_definition_accepts_string_values():
    v = VariableDefinition(
        name="electrode",
        type="categorical",
        values="electrode (2-96)",
        description="",
    )
    assert v.values == [2, 96]


def test_experiment_plan_accepts_string_variable_values():
    plan = ExperimentPlan.model_validate(
        {
            "title": "t",
            "description": "d",
            "hypothesis": {
                "statement": "s",
                "rationale": "r",
                "expected_outcome": "e",
            },
            "methodology": "m",
            "independent_variables": [
                {
                    "name": "condition_idx",
                    "type": "ordinal",
                    "values": "condition_idx (0-119)",
                }
            ],
            "control_variables": [
                {"name": "electrode", "type": "categorical", "values": "electrode (2-96)"},
                {"name": "movie_id", "type": "ordinal", "values": "movie_id (0-12)"},
                {"name": "segment_id", "type": "ordinal", "values": "segment_id (0-29)"},
            ],
        }
    )
    assert plan.independent_variables[0].values == [0, 119]
    assert plan.control_variables[0].values == [2, 96]
    assert plan.control_variables[1].values == list(range(0, 13))
    assert plan.control_variables[2].values == list(range(0, 30))
