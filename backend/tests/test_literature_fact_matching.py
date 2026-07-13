"""文献 fact_id 匹配与最小证据链构建测试。"""
from app.services.literature_search_utils import (
    build_minimal_evidence_chain,
    match_literature_facts,
)


def test_match_literature_facts_exact_and_suffix():
    facts = [
        {"fact_id": "paper_fact_001", "fact_text": "A", "content": "A"},
        {"fact_id": "paper_fact_002", "fact_text": "B", "content": "B"},
        {"fact_id": "fact_003", "fact_text": "C", "content": "C"},
    ]
    matched = match_literature_facts(facts, ["fact_001", "paper_fact_002"])
    ids = {f["fact_id"] for f in matched}
    assert ids == {"paper_fact_001", "paper_fact_002"}


def test_build_minimal_evidence_chain():
    facts = [{"fact_id": "paper_fact_001", "fact_text": "跌倒检测在联邦场景下数据异构", "source_paper_title": "Paper A"}]
    chain = build_minimal_evidence_chain("假设 H1", facts)
    assert chain["final_version"] == "假设 H1"
    assert len(chain["supporting_evidence"]) == 1
    assert chain["supporting_evidence"][0]["claim"] == "跌倒检测在联邦场景下数据异构"
