"""experiment_spec 与 Phase A 脚本链路回归测试。"""
from __future__ import annotations

from unittest.mock import patch

from app.services.data_finder_slim import slim_stage_output
from app.services.experiment_spec_service import (
    build_default_spec_from_datasets,
    normalize_experiment_spec,
    validate_spec_against_datasets,
)


def test_build_default_spec_picks_outcome_column():
    spec = build_default_spec_from_datasets([
        {
            "filename": "hepar.csv",
            "data_type": "tabular",
            "columns": ["age", "jaundice", "carcinoma", "fibrosis"],
            "dtypes": {"carcinoma": "VARCHAR"},
        },
    ], hypothesis="验证 carcinoma 与 jaundice 的关系")
    assert spec["target_column"] == "carcinoma"
    assert "age" in spec["feature_columns"]
    assert spec["primary_metric"] == "accuracy"


def test_validate_spec_reports_missing_columns():
    spec = normalize_experiment_spec({
        "target_column": "label",
        "feature_columns": ["age", "missing_col"],
    })
    gaps = validate_spec_against_datasets(spec, [{
        "columns": ["age", "weight"],
        "data_type": "tabular",
    }])
    assert any("label" in g for g in gaps)
    assert any("missing_col" in g for g in gaps)


def test_slim_experiment_design_preserves_spec_and_truncates_script():
    huge_script = "print('x')\n" * 5000
    out = {
        "methods": "m",
        "experiment_spec": {
            "target_column": "carcinoma",
            "feature_columns": [f"f{i}" for i in range(30)],
            "baselines": ["A", "B"],
            "primary_metric": "accuracy",
            "encoding_notes": "x" * 1000,
        },
        "analysis_script": huge_script,
    }
    slim = slim_stage_output(out, stage_key="experiment_design")
    assert slim["experiment_spec"]["target_column"] == "carcinoma"
    assert slim["experiment_spec"]["feature_columns_count"] == 30
    assert isinstance(slim["analysis_script"], dict)
    assert slim["analysis_script"]["_truncated"] is True


def test_small_validation_prefers_design_script():
    from app.agents.small_validation_agent import SmallValidationAgent

    agent = SmallValidationAgent()
    design_script = "import os\nprint('from_design')"
    script, source = agent._resolve_analysis_script(
        hypothesis="H",
        methods="m",
        datasets="d",
        metrics="acc",
        has_csv_data=True,
        csv_data_path="/tmp/a.csv",
        experiment_design={
            "analysis_script": design_script,
            "experiment_spec": {"primary_metric": "accuracy"},
        },
    )
    assert source == "experiment_design"
    assert "from_design" in script


def test_small_validation_fallback_when_design_script_missing():
    from app.agents.small_validation_agent import SmallValidationAgent

    agent = SmallValidationAgent()
    with patch("app.agents.small_validation_agent.generate_analysis_script", return_value="# fallback"):
        script, source = agent._resolve_analysis_script(
            hypothesis="H",
            methods="m",
            datasets="d",
            metrics="acc",
            has_csv_data=True,
            csv_data_path="/tmp/a.csv",
            experiment_design={"experiment_spec": {"primary_metric": "f1_score"}},
        )
    assert source == "small_validation_from_spec"
    assert script == "# fallback"
