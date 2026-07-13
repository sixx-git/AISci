"""experiment_spec 与数据不匹配说明回归测试。"""
from app.services.experiment_spec_service import (
    assess_validation_readiness,
    reconcile_experiment_spec_with_datasets,
)
from app.services.validation_data_guidance_service import (
    _domain_hint_datasets,
    build_validation_data_guidance,
)


def test_reconcile_carcinoma_template_against_fhir_columns():
    spec, notes = reconcile_experiment_spec_with_datasets(
        {
            "target_column": "carcinoma",
            "feature_columns": ["age", "jaundice"],
            "primary_metric": "accuracy",
        },
        [{
            "filename": "FHIR.csv",
            "columns": ["Indicator ID", "Score Rater A", "Motivation"],
        }],
        hypothesis="联邦学习 F1 提升",
    )
    assert any("模板" in n or "不一致" in n for n in notes) or spec.get("target_column") != "carcinoma"


def test_readiness_dedupes_stale_no_dataset_when_uploaded():
    readiness = assess_validation_readiness(
        {
            "hypothesis": "联邦学习",
            "data_gap": [
                "当前项目无可用数据集，且未找到匹配的公开数据集",
                "experiment_spec 目标列「carcinoma」不在已上传数据字段中",
            ],
            "data_requirements": {
                "adequacy": {
                    "status": "inadequate",
                    "mismatch_reasons": [
                        "已上传数据为合规/评分类表格，无法反映模型训练性能",
                    ],
                },
            },
            "experiment_spec": {
                "target_column": "carcinoma",
                "feature_columns": ["age"],
            },
        },
        [{"filename": "FHIR.csv", "columns": ["Indicator ID", "Score Rater A"]}],
        hypothesis="联邦学习",
    )
    blockers = readiness.get("blockers") or []
    assert not any("无可用数据集" in b for b in blockers)
    assert not any("尚未上传" in b for b in blockers)
    assert any("不匹配" in b for b in blockers)


def test_guidance_includes_domain_hints_when_api_empty():
    guidance = build_validation_data_guidance(
        {
            "hypothesis": "联邦学习 Non-IID F1 对比",
            "methods": "FedAvg vs DP",
            "metrics": "f1_score",
            "data_requirements": {
                "adequacy": {"status": "inadequate", "mismatch_reasons": ["FHIR 不合规"]},
            },
        },
        [{"filename": "FHIR.csv", "columns": ["Indicator ID"]}],
        hypothesis="联邦学习 Non-IID F1",
        fetch_downloads=False,
    )
    items = guidance.get("dataset_requirements") or []
    names = " ".join(str(i.get("name")) for i in items).lower()
    assert "leaf" in names or "huggingface" in names or "zenodo" in names
    assert guidance.get("discovery_notes") is not None or len(items) >= 2
