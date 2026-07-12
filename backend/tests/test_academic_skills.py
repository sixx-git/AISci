"""academic Skill 包已移除 — 确认注册表不再包含该目录技能"""
from app.services.skill_registry_service import discover_skills

REMOVED_ACADEMIC_SKILLS = {
    "PaperReading",
    "DeepResearch",
    "SourceTracing",
    "ResearchGenealogy",
    "ClaudeScholar",
    "PaperSkill",
    "QuestionValidator",
    "AcademicResearchSkills",
    "ResearchSkills",
    "AcademicWritingSkills",
    "WriteChinese",
    "PaperWriter",
    "AcademicPaperSkills",
    "EmpiricalPaper",
    "NaturePaper",
    "CCFASkill",
    "PaperPilot",
    "PaperToPatent",
    "PaperToStoryboard",
    "Paper2Beamer",
}


def test_academic_skills_removed_from_registry():
    skills = discover_skills(refresh=True)
    by_id = {s.id: s for s in skills}
    still_present = [sid for sid in REMOVED_ACADEMIC_SKILLS if sid in by_id]
    assert not still_present, f"应已移除的 academic skills 仍存在: {still_present}"
    assert not any(s.category == "academic" for s in skills)
