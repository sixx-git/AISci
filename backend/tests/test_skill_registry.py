"""Skill 注册表测试"""
import asyncio
import pytest

from app.services.skill_registry_service import (
    REQUIRED_SKILL_IDS,
    SkillToggleError,
    discover_skills,
    get_summary,
    is_skill_enabled,
    is_skill_locked,
    set_skill_enabled,
    list_agents,
)
from app.skills.report.plot_vlm_critique_skill import PlotVlmCritiqueSkill


def test_discover_skills_non_empty():
    skills = discover_skills(refresh=True)
    assert len(skills) >= 20
    assert all(s.id for s in skills)
    assert all(s.category_label for s in skills)


def test_required_skills_registered_and_locked():
    skills = discover_skills(refresh=True)
    by_id = {s.id: s for s in skills}
    missing = [sid for sid in REQUIRED_SKILL_IDS if sid not in by_id]
    assert not missing, f"核心 Skill 未注册: {missing}"
    for sid in REQUIRED_SKILL_IDS:
        assert by_id[sid].locked is True
        assert by_id[sid].enabled is True


def test_summary_matches_discovery():
    discover_skills(refresh=True)
    summary = get_summary()
    skills = discover_skills()
    assert summary["total"] == len(skills)
    assert summary["enabled"] + summary["disabled"] == summary["total"]
    assert summary["locked"] == sum(1 for s in skills if s.locked)


def test_toggle_skill_persists():
    discover_skills(refresh=True)
    skills = discover_skills()
    target = next((s for s in skills if not s.locked), None)
    assert target is not None, "应存在可切换的非核心 Skill"
    original = target.enabled

    set_skill_enabled(target.id, not original)
    assert is_skill_enabled(target.id) == (not original)

    set_skill_enabled(target.id, original)
    assert is_skill_enabled(target.id) == original


def test_locked_skill_cannot_toggle():
    discover_skills(refresh=True)
    locked_id = next(iter(REQUIRED_SKILL_IDS))
    assert is_skill_locked(locked_id)

    with pytest.raises(SkillToggleError):
        set_skill_enabled(locked_id, False)

    assert is_skill_enabled(locked_id) is True


def test_list_agents_has_bindings():
    discover_skills(refresh=True)
    agents = list_agents()
    assert len(agents) >= 5
    assert any(a["agent"] == "文献挖掘 Agent" for a in agents)


def test_disabled_skill_skips_at_runtime():
    discover_skills(refresh=True)
    skill_id = "PlotVlmCritique"
    assert not is_skill_locked(skill_id)
    original = is_skill_enabled(skill_id)

    try:
        set_skill_enabled(skill_id, False)
        skill = PlotVlmCritiqueSkill()
        result = asyncio.run(skill.run({}, {"stage": "test"}))
        assert result.success is True
        assert result.data.get("skipped") is True
        assert result.data.get("skill") == skill_id
        assert any("禁用" in w for w in result.warnings)
    finally:
        set_skill_enabled(skill_id, original)
