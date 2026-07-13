"""validation_data_guidance_service 回归测试。"""
from app.services.validation_data_guidance_service import (
    UPLOAD_REQUIRED,
    UPLOAD_SKIP_OK,
    build_validation_data_guidance,
)


def test_build_validation_data_guidance_marks_required_and_skip_ok():
    guidance = build_validation_data_guidance(
        {
            "hypothesis": "联邦学习 F1 提升",
            "data_requirements": {
                "adequacy": {
                    "status": "inadequate",
                    "mismatch_reasons": ["FHIR 合规表无法验证联邦学习 F1"],
                    "what_hypothesis_needs": ["client_id", "accuracy", "f1_score"],
                    "what_uploaded_can_do": ["合规评分统计"],
                    "required_datasets": [{
                        "name": "联邦学习 benchmark",
                        "description": "含 client_id 与 accuracy 列",
                        "modality": "tabular",
                        "required_columns": ["client_id", "accuracy"],
                    }],
                },
                "recommended_public_datasets": [{
                    "dataset_name": "LEAF FedAvg results",
                    "source_platform": "Zenodo",
                    "download_url": "https://zenodo.org/record/example",
                    "description": "联邦学习基准结果",
                }],
                "required_columns": ["client_id", "accuracy"],
            },
        },
        [{
            "filename": "FHIR.csv",
            "data_type": "tabular",
            "columns": ["Indicator ID", "Score Rater A"],
        }],
        hypothesis="联邦学习 F1 提升",
        blockers=["已上传数据与假设验证目标不匹配"],
        fetch_downloads=False,
    )

    assert "FHIR" in (guidance.get("summary") or "") or guidance.get("mismatch_reasons")
    items = guidance.get("dataset_requirements") or []
    assert any(i.get("upload_requirement") == UPLOAD_REQUIRED for i in items)
    assert any(i.get("upload_requirement") == UPLOAD_SKIP_OK for i in items)
    assert any(i.get("download_url") for i in items)
    assert guidance.get("must_upload_count", 0) >= 1
    assert guidance.get("next_steps")


def test_small_validation_blocked_includes_guidance(monkeypatch, tmp_path):
    from app.agents.small_validation_agent import SmallValidationAgent

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

    with monkeypatch.context() as m:
        m.setattr(agent, "_save_validation_files", lambda *a, **k: "vid")
        result = agent.generate_validation(
            hypothesis="联邦学习",
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
            run_id="run-guidance-test",
        )

    assert result.get("validation_status") == "blocked"
    assert result.get("validation_data_guidance")
    assert result["validation_data_guidance"].get("must_upload_count") == 1
    assert result.get("hypothesis") == "联邦学习"
