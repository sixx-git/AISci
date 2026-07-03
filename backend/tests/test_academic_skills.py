"""学术 Skills 注册发现测试。"""
from app.services.skill_registry_service import discover_skills

EXPECTED_ACADEMIC_SKILLS = {
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


def test_academic_skills_discovered():
    skills = discover_skills(refresh=True)
    found = {s.name for s in skills if s.category == "academic"}
    missing = EXPECTED_ACADEMIC_SKILLS - found
    assert not missing, f"未发现的 academic skills: {missing}"
    assert len(found) >= len(EXPECTED_ACADEMIC_SKILLS)


def test_academic_skills_have_consumers():
    skills = discover_skills(refresh=True)
    academic = [s for s in skills if s.name in EXPECTED_ACADEMIC_SKILLS]
    assert len(academic) == len(EXPECTED_ACADEMIC_SKILLS)
    linked = [s for s in academic if s.agents]
    assert len(linked) >= 18
