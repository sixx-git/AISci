"""报告合规指标重算测试"""
from app.services.report_compliance_service import (
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
