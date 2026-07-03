"""学术写作与论文辅助 Skills（适配外部 Academic-* / Paper-* 能力清单）。"""
from app.skills.academic.literature_academic_skill import (
    PaperReadingSkill,
    DeepResearchSkill,
    SourceTracingSkill,
    ResearchGenealogySkill,
    ClaudeScholarSkill,
    PaperSkill,
)
from app.skills.academic.research_academic_skill import (
    QuestionValidatorSkill,
    AcademicResearchSkills,
    ResearchSkills,
)
from app.skills.academic.writing_academic_skill import (
    AcademicWritingSkills,
    WriteChineseSkill,
    PaperWriterSkill,
    AcademicPaperSkills,
)
from app.skills.academic.report_format_academic_skill import (
    EmpiricalPaperSkill,
    NaturePaperSkill,
    CCFASkill,
    PaperPilotSkill,
)
from app.skills.academic.derivative_academic_skill import (
    PaperToPatentSkill,
    PaperToStoryboardSkill,
    Paper2BeamerSkill,
)

__all__ = [
    "PaperReadingSkill",
    "DeepResearchSkill",
    "SourceTracingSkill",
    "ResearchGenealogySkill",
    "ClaudeScholarSkill",
    "PaperSkill",
    "QuestionValidatorSkill",
    "AcademicResearchSkills",
    "ResearchSkills",
    "AcademicWritingSkills",
    "WriteChineseSkill",
    "PaperWriterSkill",
    "AcademicPaperSkills",
    "EmpiricalPaperSkill",
    "NaturePaperSkill",
    "CCFASkill",
    "PaperPilotSkill",
    "PaperToPatentSkill",
    "PaperToStoryboardSkill",
    "Paper2BeamerSkill",
]
