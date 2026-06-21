"""Discovery 文献刷新与合并单元测试"""
from app.agents.literature_mining_agent import LiteratureMiningAgent
from app.services.pipeline_service import PipelineService


def test_merge_mining_dicts_dedupes_facts():
    previous = {
        "facts": [{"fact_id": "f1", "content": "old fact"}],
        "citation_map": [{"document_id": "d1", "title": "Paper A"}],
        "source_papers": ["Paper A"],
        "retrieved_papers": [{"title": "Paper A"}],
    }
    fresh = {
        "facts": [
            {"fact_id": "f1", "content": "old fact updated"},
            {"fact_id": "f2", "content": "new fact"},
        ],
        "citation_map": [{"document_id": "d2", "title": "Paper B"}],
        "source_papers": ["Paper B"],
        "retrieved_papers": [{"title": "Paper B"}],
    }

    merged = LiteratureMiningAgent._merge_mining_dicts(
        previous,
        fresh,
        discovery_round=2,
        search_query="expanded query",
        supplementary_import=True,
    )

    assert len(merged["facts"]) == 2
    assert merged["facts"][0]["fact_id"] == "f1"
    assert len(merged["citation_map"]) == 2
    assert merged["discovery_refresh"]["merged_from_previous"] is True
    assert merged["discovery_refresh"]["new_facts"] == 1


def test_build_discovery_refined_context():
    svc = PipelineService(db=None)  # type: ignore[arg-type]
    ctx = svc._build_discovery_refined_context(
        {
            "ideation_novelty": {
                "suggested_angles": ["方向A", "方向B"],
                "avoid_topics": ["饱和主题"],
            },
            "knowledge_gap": {
                "knowledge_gaps": [{"gap": "缺少纵向数据"}],
            },
            "problem_understanding": {"keywords": ["microbiome", "cognition"]},
        },
        ["证据不足", "方法需细化"],
    )
    assert "方向A" in ctx["keywords"] or "方向A" in ctx["refinement_queries"]
    assert len(ctx["refinement_queries"]) >= 2
