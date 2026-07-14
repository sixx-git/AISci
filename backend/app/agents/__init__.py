"""
智能体 (Agents) 模块
"""
from app.agents.problem_understanding_agent import (
    ProblemUnderstandingAgent,
    ProblemUnderstandingRequest,
    ProblemUnderstandingResponse,
    get_problem_understanding_agent
)
from app.agents.literature_mining_agent import (
    LiteratureMiningAgent,
    LiteratureMiningRequest,
    LiteratureMiningResponse,
    ScienceFact,
    EvidenceItem,
    CitationMapItem,
    get_literature_mining_agent
)
from app.agents.knowledge_gap_agent import (
    KnowledgeGapAgent,
    KnowledgeGapRequest,
    KnowledgeGapResponse,
    KnownFactSummary,
    KnowledgeGapItem,
    ContradictionItem,
    PossibleConnectionItem,
    ResearchOpportunityItem,
    get_knowledge_gap_agent
)
from app.agents.hypothesis_generation_agent import (
    HypothesisGenerationAgent,
    HypothesisItem,
    HypothesisGenerationResult,
    get_hypothesis_generation_agent
)
from app.agents.hypothesis_review_agent import (
    HypothesisReviewAgent,
    HypothesisCandidate,
    HypothesisReviewRequest,
    HypothesisReviewResult,
    ScoreDetail,
    HypothesisScores,
    HypothesisReview,
    get_hypothesis_review_agent
)
from app.agents.report_generation_agent import (
    ReportGenerationAgent,
    get_report_generation_agent
)

__all__ = [
    'ProblemUnderstandingAgent',
    'ProblemUnderstandingRequest',
    'ProblemUnderstandingResponse',
    'get_problem_understanding_agent',
    'LiteratureMiningAgent',
    'LiteratureMiningRequest',
    'LiteratureMiningResponse',
    'ScienceFact',
    'EvidenceItem',
    'CitationMapItem',
    'get_literature_mining_agent',
    'KnowledgeGapAgent',
    'KnowledgeGapRequest',
    'KnowledgeGapResponse',
    'KnownFactSummary',
    'KnowledgeGapItem',
    'ContradictionItem',
    'PossibleConnectionItem',
    'ResearchOpportunityItem',
    'get_knowledge_gap_agent',
    'HypothesisGenerationAgent',
    'HypothesisItem',
    'HypothesisGenerationResult',
    'get_hypothesis_generation_agent',
    'HypothesisReviewAgent',
    'HypothesisCandidate',
    'HypothesisReviewRequest',
    'HypothesisReviewResult',
    'ScoreDetail',
    'HypothesisScores',
    'HypothesisReview',
    'get_hypothesis_review_agent',
    'ReportGenerationAgent',
    'get_report_generation_agent',
]
