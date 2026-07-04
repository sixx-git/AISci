"""报告合规指标重算测试"""
from app.services.report_compliance_service import (
    assess_experiments_chapter,
    assess_pipeline_experiment_design,
    evaluate_chapter_item_status,
    is_placeholder_reference,
    parse_report_references,
    reconcile_reference_check,
    refresh_compliance_metrics,
)


def test_parse_report_references_json():
    raw = '["Author. Paper A (2024). https://arxiv.org/abs/1234"]'
    refs = parse_report_references(raw)
    assert len(refs) == 1
    assert "Paper A" in refs[0]


def test_reconcile_reference_with_citation_map():
    citation_map = [
        {
            "title": "Deep Learning for Science",
            "authors": "Zhang, L.",
            "year": 2024,
            "source_url": "https://arxiv.org/abs/2401.00001",
        }
    ]
    references = [
        "Zhang, L. Deep Learning for Science (2024). https://arxiv.org/abs/2401.00001"
    ]
    check = reconcile_reference_check(references, citation_map, citation_map, [])
    assert check["verified_count"] == 1
    assert check["suspicious_count"] == 0


def test_reconcile_fallback_when_corpus_present():
    citation_map = [{"title": "BERT", "authors": "Devlin", "year": 2019}]
    references = ["Devlin. BERT (2019). https://arxiv.org/abs/1810.04805"]
    check = reconcile_reference_check(references, citation_map, citation_map, [])
    assert check["verified_count"] >= 1


def test_refresh_compliance_updates_zero_metrics():
    compliance = {
        "references_verified": 0,
        "evidence_fact_count": 0,
        "hypothesis_with_evidence_count": 0,
        "items": [{"key": "references", "label": "12. References", "status": "missing", "note": "x"}],
        "critical_issues": ["参考文献缺失或未验证，不符合赛题要求"],
    }
    citation_map = [{"title": "Test Paper", "authors": "A. Author", "year": 2023}]
    refs = ["A. Author. Test Paper (2023). https://example.org/paper"]
    facts = [{"fact_id": "f1", "content": "finding", "source_paper_title": "Test Paper"}]
    refreshed = refresh_compliance_metrics(
        compliance,
        references=refs,
        citation_map=citation_map,
        verified_references=citation_map,
        literature_facts=facts,
        hypotheses=[{"hypothesis": "h1", "supporting_fact_ids": ["f1"]}],
    )
    assert refreshed["references_verified"] == 1
    assert refreshed["evidence_fact_count"] == 1
    assert refreshed["hypothesis_with_evidence_count"] == 1
    assert refreshed["has_references"] is True
    ref_item = next(i for i in refreshed["items"] if i["key"] == "references")
    assert ref_item["status"] == "completed"


def test_placeholder_reference_detected():
    assert is_placeholder_reference("缺少真实引用，需先导入 arXiv/BibTeX/PDF 文献。")
    assert not is_placeholder_reference("Smith, J. A real paper title from arxiv (2024). https://arxiv.org/abs/1234")


def test_experiments_dict_chapter_not_marked_missing():
    chapter = {
        "baselines": [{"name": "RF", "description": "Random Forest baseline"}],
        "metrics": [{"name": "AUC", "description": "Area under curve"}],
        "experimental_setup": "",
        "ablation_study": [],
        "validation_protocol": "",
    }
    assert assess_experiments_chapter(chapter) == "complete"
    status, _ = evaluate_chapter_item_status("experiments", chapter)
    assert status == "completed"


def test_experiments_from_pipeline_when_report_chapter_empty():
    experiment_design = {
        "baselines": '[{"name": "XGBoost"}]',
        "metrics": '[{"name": "RMSE"}]',
        "experimental_steps": "1. Train\n2. Evaluate",
        "expected_results": "RMSE should decrease",
    }
    assert assess_pipeline_experiment_design(experiment_design) == "complete"
    status, note = evaluate_chapter_item_status("experiments", {}, experiment_design=experiment_design)
    assert status == "completed"
    assert note is not None


def test_refresh_compliance_updates_experiments_item():
    compliance = {
        "has_experiments": False,
        "items": [
            {"key": "experiments", "label": "10. Experiments", "status": "missing", "note": "该字段缺失"},
            {"key": "references", "label": "12. References", "status": "missing", "note": "x"},
        ],
        "completed": 0,
        "missing": 2,
        "human_review": 0,
    }
    experiment_design = {
        "baselines": "Baseline A",
        "metrics": "Accuracy",
        "experimental_steps": "Step 1: split data",
        "expected_results": "Higher accuracy than baseline",
    }
    refreshed = refresh_compliance_metrics(
        compliance,
        references=[],
        chapters={"experiments": "{}", "results": ""},
        experiment_design=experiment_design,
    )
    exp_item = next(i for i in refreshed["items"] if i["key"] == "experiments")
    assert exp_item["status"] == "completed"
    assert refreshed["has_experiments"] is True
    assert refreshed["completed"] == 1


def test_assess_result_type_simulated_json():
    chapter = {
        "actual_results": [],
        "simulated_results": ["合并 CSV 3813 行"],
        "expected_results": ["待验证"],
        "limitations": [],
    }
    has_result, rtype = __import__(
        "app.services.report_compliance_service", fromlist=["assess_result_type"]
    ).assess_result_type(chapter)
    assert has_result is True
    assert rtype == "simulated_result"


def test_refresh_compliance_updates_datasets_and_result_flags():
    from app.services.report_compliance_service import assess_result_type, refresh_compliance_metrics

    compliance = {
        "result_type": "none",
        "has_datasets": False,
        "has_source": False,
        "warnings": [
            "数据集来源不足，请补充真实或合规数据来源",
            "当前仅有预期结果，建议补充公式推导、模拟验证或小样实验",
        ],
    }
    chapters = {
        "datasets": "JWST FITS 上传，3813 行合并 CSV",
        "source": "Planck CMB 与 BAO 巡天数据提供宇宙学参数",
        "target": "轨道衰减率与潮汐耗散系数",
        "results": {
            "actual_results": [],
            "simulated_results": ["data_finder 合并 CSV 3813 行"],
            "expected_results": [],
            "limitations": [],
        },
    }
    refreshed = refresh_compliance_metrics(
        compliance,
        references=["Smith. Paper (2024). https://arxiv.org/abs/1234"],
        chapters=chapters,
    )
    assert refreshed["has_datasets"] is True
    assert refreshed["has_source"] is True
    assert refreshed["result_type"] == "simulated_result"
    assert not any("数据集来源不足" in w for w in refreshed.get("warnings") or [])
    assert not any("仅有预期结果" in w for w in refreshed.get("warnings") or [])
