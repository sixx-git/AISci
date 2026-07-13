"""DataAdequacyAssessmentSkill 回归测试。"""
from __future__ import annotations

from unittest.mock import patch

from app.skills.data.data_adequacy_assessment_skill import (
    DataAdequacyAssessmentSkill,
    merge_adequacy_into_experiment_design,
    resolve_next_action,
    resolve_upload_status,
    rule_fallback_adequacy,
)


FHIR_DATASETS = [{
    "filename": "FHIR.csv",
    "n_rows": 41,
    "n_columns": 7,
    "columns": ["Indicator ID", "Score Rater A", "Motivation Rater A", "Final Score"],
    "semantic_schema": {"recommended_targets": ["Final Score"]},
}]


def test_rule_fallback_fhir_vs_gan_hypothesis():
    payload = rule_fallback_adequacy(
        hypothesis="使用 GAN 提升联邦学习隐私保护效果",
        required_data="联邦学习 benchmark，含 accuracy 与 communication_cost",
        validation_target="global_accuracy",
        uploaded_datasets=FHIR_DATASETS,
    )
    assert payload["status"] == "inadequate"
    assert payload["mismatch_reasons"]
    assert "FHIR" in payload["mismatch_reasons"][0] or "合规" in payload["mismatch_reasons"][0]


def test_resolve_upload_status_inadequate():
    adequacy = {"status": "inadequate"}
    assert resolve_upload_status(adequacy, 1) == "inadequate"
    assert resolve_next_action(adequacy, 1) == "download_recommended"


def test_merge_adequacy_sets_validation_blocked():
    ed = {"data_gap": []}
    adequacy = rule_fallback_adequacy(
        hypothesis="GAN federated learning",
        required_data="benchmark",
        validation_target="accuracy",
        uploaded_datasets=FHIR_DATASETS,
    )
    merge_adequacy_into_experiment_design(ed, adequacy, round_id="run-1")
    assert ed.get("validation_blocked") is True
    assert len(ed.get("data_gap") or []) > 0


async def _run_skill(**kwargs):
    skill = DataAdequacyAssessmentSkill()
    return await skill.run(input_data=kwargs, context={})


def test_skill_empty_upload():
    import asyncio

    result = asyncio.run(_run_skill(
        hypothesis="test",
        uploaded_datasets=[],
    ))
    assert result.success
    assert result.data.get("status") == "inadequate"


def test_plan_executability_blocks_inadequate():
    from app.core.plan_executability import assess_plan_executability

    ed = {
        "methods": "train gan",
        "metrics": "accuracy",
        "experimental_steps": "step1",
        "data_requirements": {
            "adequacy": {
                "status": "inadequate",
                "mismatch_reasons": ["FHIR 评分无法验证 GAN"],
            },
        },
        "validation_blocked": True,
        "project_datasets": FHIR_DATASETS,
    }
    gate = assess_plan_executability(ed, {"datasets": FHIR_DATASETS})
    assert gate.get("passed") is False
    assert any("不匹配" in b for b in (gate.get("blockers") or []))
