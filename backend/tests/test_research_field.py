"""研究领域推断与外部数据候选过滤测试"""
from app.core.research_field import (
    build_external_search_query,
    filter_relevant_external_candidates,
    infer_research_field,
    is_actionable_dataset_candidate,
    score_external_candidate,
    should_search_biomedical_sources,
)
from app.services.external_candidate_service import list_manual_candidates


def test_infer_astronomy_field():
    q = "为什么行星的轨道没有衰减并导致它们相互碰撞？"
    domain = "天体物理学与轨道动力学"
    assert infer_research_field(research_question=q, research_domain=domain) == "astronomy_physics"


def test_skip_biomedical_sources_for_astronomy():
    ctx = {
        "field": "astronomy_physics",
        "research_question": "行星轨道稳定性",
        "research_domain": "天文学",
        "query_terms": ["行星", "轨道", "planetary", "orbit"],
        "data_spec": {},
    }
    assert should_search_biomedical_sources(ctx) is False


def test_filter_out_irrelevant_geo_for_astronomy():
    ctx = {
        "field": "astronomy_physics",
        "research_question": "为什么行星的轨道没有衰减？",
        "research_domain": "天体物理学",
        "query_terms": ["行星", "轨道", "planetary", "orbit", "solar"],
        "data_spec": {"domain_keywords": ["planetary orbit"]},
    }
    candidates = [
        {
            "source_platform": "NCBI GEO",
            "dataset_name": "Phenotypic CRISPR screening trophoblast",
            "description": "gene expression cell line cancer",
            "confidence": 0.68,
        },
        {
            "source_platform": "Zenodo",
            "dataset_name": "Solar system planetary ephemeris dataset",
            "description": "orbital elements for planets around the Sun",
            "confidence": 0.72,
        },
    ]
    filtered = filter_relevant_external_candidates(candidates, ctx, min_score=0.25)
    names = [c["dataset_name"] for c in filtered]
    assert any("ephemeris" in n.lower() or "planetary" in n.lower() for n in names)
    assert not any("crispr" in n.lower() for n in names)


def test_openalex_not_actionable_manual_candidate():
    manual = list_manual_candidates([
        {
            "candidate_id": "c1",
            "source_platform": "OpenAlex",
            "dataset_name": "Some paper title",
            "availability": "reference_only",
            "import_supported": False,
        }
    ])
    assert manual == []


def test_build_external_search_query_prefers_english_keywords():
    ctx = {
        "field": "astronomy_physics",
        "research_question": "为什么行星的轨道没有衰减？",
        "research_domain": "天体物理学",
        "data_spec": {
            "domain_keywords": ["planetary orbit", "orbital decay"],
            "dataset_keywords": ["solar system"],
        },
    }
    q = build_external_search_query(ctx)
    assert "planetary" in q.lower() or "orbit" in q.lower()


def test_score_penalizes_biomed_noise():
    ctx = {
        "field": "astronomy_physics",
        "research_question": "行星轨道",
        "research_domain": "天文学",
        "query_terms": ["行星", "轨道", "planetary"],
        "data_spec": {},
    }
    geo = score_external_candidate(
        {
            "source_platform": "NCBI GEO",
            "dataset_name": "CRISPR cancer cell line",
            "description": "gene expression",
        },
        ctx,
    )
    astro = score_external_candidate(
        {
            "source_platform": "Zenodo",
            "dataset_name": "Planetary orbital stability simulation data",
            "description": "solar system orbit integration",
        },
        ctx,
    )
    assert astro > geo
