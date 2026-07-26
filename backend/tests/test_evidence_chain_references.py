"""证据链不得覆盖已有真实书目。"""
from app.agents.report_generation_agent import ReportGenerationAgent


def test_evidence_chain_does_not_overwrite_real_bibliography():
    result = {
        "chapters": {
            "references": [
                "姜启源, 谢金星, 叶俊. 数学模型[M]. 北京: 高等教育出版社, 2018.",
            ]
        }
    }
    hypotheses = [
        {
            "evidence_chain": {
                "supporting_evidence": [
                    {"source_title": "Some Evidence Paper", "year": "2020", "doi": "10.1/x"}
                ]
            }
        }
    ]
    out = ReportGenerationAgent._apply_evidence_chain_references(result, hypotheses)
    assert out["chapters"]["references"][0].startswith("姜启源")
    assert "Some Evidence Paper" not in out["chapters"]["references"][0]


def test_evidence_chain_fills_when_bibliography_empty():
    result = {"chapters": {"references": []}}
    hypotheses = [
        {
            "evidence_chain": {
                "supporting_evidence": [
                    {"source_title": "Some Evidence Paper", "year": "2020", "doi": "10.1/x"}
                ]
            }
        }
    ]
    out = ReportGenerationAgent._apply_evidence_chain_references(result, hypotheses)
    assert any("Some Evidence Paper" in r for r in out["chapters"]["references"])
