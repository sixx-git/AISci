"""领域数据目录 — SJTU 学科 → 数据采集检索词"""
from app.core.domain_data_catalog import (
    enrich_data_spec_from_domain,
    field_from_category,
    get_catalog_fallbacks,
    get_search_seed,
    infer_field_from_text,
    merge_domain_hints_into_config,
    parse_category_from_description,
)
from app.core.research_field import build_external_search_query, build_research_context, infer_research_field


def test_parse_category_from_sjtu_file_description():
    fd = "领域：天文学。巡天观测、宇宙学模拟、天体物理开放目录数据。背景摘要：..."
    assert parse_category_from_description(fd) == "天文学"


def test_field_from_sjtu_categories():
    assert field_from_category("天文学") == "astronomy_physics"
    assert field_from_category("化学") == "chemistry"
    assert field_from_category("神经科学") == "neuroscience"
    assert field_from_category("人工智能") == "cs_ai"


def test_enrich_astronomy_data_spec():
    fd = "领域：天文学。巡天观测、宇宙学模拟、天体物理开放目录数据。"
    spec = enrich_data_spec_from_domain(
        {"research_question": "宇宙的形状是什么？"},
        research_domain="天文学",
        file_description=fd,
    )
    assert spec["research_field_inferred"] == "astronomy_physics"
    assert "astronomy" in [k.lower() for k in spec.get("domain_keywords", [])]
    assert "external_search_seed" in spec
    assert "cosmology" in spec["external_search_seed"]


def test_enrich_chemistry_data_spec():
    fd = "领域：化学。分子结构数据库、材料性能数据、电化学与储能实验数据。"
    spec = enrich_data_spec_from_domain({}, research_domain="化学", file_description=fd)
    assert spec["research_field_inferred"] == "chemistry"
    assert get_search_seed("chemistry") in spec["external_search_seed"]


def test_merge_domain_hints_for_quick_report():
    hints = merge_domain_hints_into_config(
        {"data_need_note": "领域：生态学。气候/遥感、物种与农业生态系统监测数据。"},
    )
    assert hints.get("research_field") == "earth_environment"
    assert hints.get("domain_keywords")


def test_infer_field_prefers_category_over_generic_tokens():
    fd = "领域：能源科学。能源系统运行数据、氢能/核能相关实验与仿真数据。"
    assert infer_field_from_text(file_description=fd) == "energy_science"


def test_build_external_search_uses_catalog_seed():
    spec = enrich_data_spec_from_domain(
        {},
        research_domain="神经科学",
        file_description="领域：神经科学。脑成像、神经电生理。",
    )
    ctx = build_research_context(
        research_question="记忆如何形成？",
        research_domain="神经科学",
        data_spec=spec,
    )
    q = build_external_search_query(ctx)
    assert "neuro" in q.lower() or "brain" in q.lower() or "fmri" in q.lower()


def test_catalog_fallbacks_cover_all_sjtu_fields():
    categories = [
        "天文学", "化学", "医学与健康", "生物学", "物理学",
        "工程与材料科学", "信息科学", "神经科学", "生态学", "能源科学", "人工智能", "数学科学",
    ]
    for cat in categories:
        field = field_from_category(cat)
        assert field != "general", cat
        fallbacks = get_catalog_fallbacks(field)
        assert len(fallbacks) >= 3, cat


def test_infer_research_field_from_category_in_domain():
    assert infer_research_field(research_domain="化学") == "chemistry"
    assert infer_research_field(research_domain="Mathematical Sciences") == "math_science"
