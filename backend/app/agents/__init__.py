"""
智能体 (Agents) 模块
"""
from app.agents.problem_understanding_agent import (
    ProblemUnderstandingAgent,
    ProblemUnderstandingRequest,
    ProblemUnderstandingResponse
)
from app.agents.literature_mining_agent import (
    LiteratureMiningAgent,
    LiteratureMiningRequest,
    LiteratureMiningResponse,
    ScienceFact,
    EvidenceItem,
    CitationMapItem
)
from app.agents.knowledge_gap_agent import (
    KnowledgeGapAgent,
    KnowledgeGapRequest,
    KnowledgeGapResponse,
    KnownFactSummary,
    KnowledgeGapItem,
    ContradictionItem,
    PossibleConnectionItem,
    ResearchOpportunityItem
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
from app.agents.experiment_design_agent import (
    ExperimentDesignAgent,
    get_experiment_design_agent
)
from app.agents.small_validation_agent import (
    SmallValidationAgent,
    get_small_validation_agent
)

__all__ = [
    'ProblemUnderstandingAgent',
    'ProblemUnderstandingRequest',
    'ProblemUnderstandingResponse',
    'LiteratureMiningAgent',
    'LiteratureMiningRequest',
    'LiteratureMiningResponse',
    'ScienceFact',
    'EvidenceItem',
    'CitationMapItem',
    'KnowledgeGapAgent',
    'KnowledgeGapRequest',
    'KnowledgeGapResponse',
    'KnownFactSummary',
    'KnowledgeGapItem',
    'ContradictionItem',
    'PossibleConnectionItem',
    'ResearchOpportunityItem',
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
    'ExperimentDesignAgent',
    'get_experiment_design_agent',
    'SmallValidationAgent',
    'get_small_validation_agent',
]
