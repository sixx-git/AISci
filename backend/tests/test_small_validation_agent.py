"""小样验证 Agent 测试。"""
from app.agents.small_validation_agent import SmallValidationAgent


def test_build_categorized_results_blocked():
    agent = SmallValidationAgent()
    result = agent._build_categorized_results(
        {"has_real_data": 0, "validation_status": "blocked"},
        hypothesis="联邦学习 F1 提升",
        experiment_design={"metrics": "f1", "expected_results": "F1 提升"},
        modeling_results=None,
    )
    assert result["result_type_summary"] == "none"
    assert "联邦学习" in result["expected_results"]["hypothesis"]


def test_build_categorized_results_sandbox_success():
    agent = SmallValidationAgent()
    result = agent._build_categorized_results(
        {
            "has_real_data": 1,
            "validation_status": "completed",
            "sandbox_execution": {
                "success": True,
                "metrics": {"f1_score": 0.82},
                "plots": [{"plot_id": "comparison"}],
            },
        },
        hypothesis="H1",
        experiment_design={},
        modeling_results=None,
    )
    assert result["result_type_summary"] == "has_actual_results"
    assert result["actual_results"]["sandbox_metrics"]["f1_score"] == 0.82


def test_generate_validation_writes_hypothesis_and_blocked(monkeypatch, tmp_path):
    agent = SmallValidationAgent()
    csv_path = tmp_path / "fhir.csv"
    csv_path.write_text("Indicator ID;Score\na1;1\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.agents.small_validation_agent.build_validation_data_guidance",
        lambda *a, **k: {
            "summary": "需要联邦 benchmark",
            "dataset_requirements": [{
                "name": "Fed benchmark",
                "upload_requirement": "required",
                "download_url": "https://example.com/data",
            }],
            "must_upload_count": 1,
        },
    )
    monkeypatch.setattr(agent, "_save_validation_files", lambda *a, **k: "vid")

    result = agent.generate_validation(
        hypothesis="联邦学习 F1 提升",
        csv_data_path=str(csv_path),
        experiment_design={
            "data_requirements": {
                "adequacy": {
                    "status": "inadequate",
                    "mismatch_reasons": ["FHIR 无法验证联邦学习"],
                },
            },
            "validation_blocked": True,
            "validation_blocked_reason": "数据不匹配",
        },
        run_id="run-test",
    )

    assert result.get("hypothesis") == "联邦学习 F1 提升"
    assert result.get("validation_status") == "blocked"
    assert result.get("has_real_data") == 0
    assert result.get("has_uploaded_data") == 1
    assert result.get("validation_data_guidance")
