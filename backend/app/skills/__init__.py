"""
科研外部 Skill 适配层
参考 Hermes / OpenScholar / AI Scientist 等科研智能体的公开能力思想，
实现为本项目内部模块。
"""
from app.skills.base import BaseSkill, SkillResult
from app.skills.literature import (
    ArxivSearchSkill,
    PdfEvidenceExtractionSkill,
    CitationGroundingSkill,
    SearchPapersSkill,
)
from app.skills.reasoning import HypothesisNoveltyReviewSkill, QuestionAlignmentSkill
from app.skills.experiment import ExperimentSanityCheckSkill
from app.skills.data import (
    DataJuicerLiteSkill,
    DatasetDiscoverySkill,
)
from app.skills.report import ScientificPlotSkill

__all__ = [
    "BaseSkill",
    "SkillResult",
    "ArxivSearchSkill",
    "PdfEvidenceExtractionSkill",
    "CitationGroundingSkill",
    "SearchPapersSkill",
    "HypothesisNoveltyReviewSkill",
    "QuestionAlignmentSkill",
    "ExperimentSanityCheckSkill",
    "DataJuicerLiteSkill",
    "DatasetDiscoverySkill",
    "ScientificPlotSkill",
]