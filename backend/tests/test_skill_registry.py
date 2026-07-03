"""Skill 注册表测试"""
from app.services.skill_registry_service import (
    discover_skills,
    get_summary,
    is_skill_enabled,
    set_skill_enabled,
    list_agents,
)


def test_discover_skills_non_empty():
    skills = discover_skills(refresh=True)
    assert len(skills) >= 20
    assert all(s.id for s in skills)
    assert all(s.category_label for s in skills)


def test_summary_matches_discovery():
    discover_skills(refresh=True)
    summary = get_summary()
    skills = discover_skills()
    assert summary["total"] == len(skills)
    assert summary["enabled"] + summary["disabled"] == summary["total"]


def test_toggle_skill_persists():
    discover_skills(refresh=True)
    skills = discover_skills()
    target = skills[0]
    original = target.enabled

    set_skill_enabled(target.id, not original)
    assert is_skill_enabled(target.id) == (not original)

    set_skill_enabled(target.id, original)
    assert is_skill_enabled(target.id) == original


def test_list_agents_has_bindings():
    discover_skills(refresh=True)
    agents = list_agents()
    assert len(agents) >= 5
    assert any(a["agent"] == "文献挖掘 Agent" for a in agents)
