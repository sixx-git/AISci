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
]
