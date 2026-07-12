"""科学自迭代 — 配置与响应 Schema"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScienceIterationConfig(BaseModel):
    """写入 project.config.science_iteration"""

    enabled: bool = True
    max_rounds: int = Field(default=2, ge=1, le=5)
    auto_triggers: List[str] = Field(
        default_factory=lambda: ["evidence_weak", "review_reject", "validation_fail"],
    )
    min_ensemble_score: float = Field(default=7.5, ge=0, le=10)
    min_evidence_facts: int = Field(default=2, ge=0, le=20)
    stagnation_delta: float = Field(default=0.5, ge=0, le=5)
    require_human_on_stagnation: bool = False
    show_iteration_in_report: bool = True
    auto_literature_on_weak_evidence: bool = True
    auto_literature_max: int = Field(default=3, ge=1, le=10)


class HypothesisOriginBlock(BaseModel):
    main_contradiction: str = ""
    phenomenon_contradiction: str = ""
    problem_statement: str = ""
    research_significance: str = ""
    reasoning_chain: List[str] = Field(default_factory=list)


class LiteratureGroundingItem(BaseModel):
    fact_id: str = ""
    content: str = ""
    quote_text: str = ""
    source_title: str = ""
    document_id: str = ""
    relevance_score: Optional[float] = None


class DataGroundingItem(BaseModel):
    table_id: str = ""
    source_title: str = ""
    source_type: str = ""
    csv_path: str = ""
    row_count: Optional[int] = None
    extraction_method: str = ""
    data_citation_id: str = ""


class HypothesisGroundingBlock(BaseModel):
    literature: List[LiteratureGroundingItem] = Field(default_factory=list)
    data: List[DataGroundingItem] = Field(default_factory=list)
    multimodal: List[Dict[str, Any]] = Field(default_factory=list)
    counter_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_gaps: List[str] = Field(default_factory=list)


class HypothesisVerificationBlock(BaseModel):
    verifiable_spec: Dict[str, Any] = Field(default_factory=dict)
    validation_target: str = ""
    expected_measurable_effect: str = ""
    verification_checks: List[Dict[str, Any]] = Field(default_factory=list)
    sandbox_success: Optional[bool] = None


class HypothesisProvenanceResponse(BaseModel):
    hypothesis_id: str
    hypothesis_text: str = ""
    origin: HypothesisOriginBlock = Field(default_factory=HypothesisOriginBlock)
    grounding: HypothesisGroundingBlock = Field(default_factory=HypothesisGroundingBlock)
    verification: HypothesisVerificationBlock = Field(default_factory=HypothesisVerificationBlock)
    evidence_sufficiency: str = ""
    evidence_level: str = "medium"
    scores: Dict[str, Any] = Field(default_factory=dict)


class MaterialSupplementAction(BaseModel):
    action_type: str
    description: str
    priority: str = "medium"
    target: str = ""


class MaterialSupplementPlan(BaseModel):
    triggers: List[str] = Field(default_factory=list)
    actions: List[MaterialSupplementAction] = Field(default_factory=list)
    suggested_queries: List[str] = Field(default_factory=list)


class IterationRoundScores(BaseModel):
    hypothesis_tree: Optional[float] = None
    ensemble_overall: Optional[float] = None
    evidence_balance: Optional[float] = None
    logic_score: Optional[float] = None
    cqs: Optional[float] = None
    gate_passed: Optional[bool] = None


class IterationRoundRecord(BaseModel):
    round: int
    trigger: str
    label: str = ""
    hypothesis_preview: str = ""
    actions_taken: List[str] = Field(default_factory=list)
    scores: IterationRoundScores = Field(default_factory=IterationRoundScores)
    delta_from_prev: Dict[str, Any] = Field(default_factory=dict)
    material_plan: Optional[MaterialSupplementPlan] = None
    snapshot_label: str = ""


class ScienceIterationSessionResponse(BaseModel):
    session_id: str
    project_id: str
    run_id: str
    config: ScienceIterationConfig = Field(default_factory=ScienceIterationConfig)
    rounds: List[IterationRoundRecord] = Field(default_factory=list)
    current_best: Dict[str, Any] = Field(default_factory=dict)
    version_snapshots: List[Dict[str, Any]] = Field(default_factory=list)
    material_supplement_plan: Optional[MaterialSupplementPlan] = None
    human_checkpoints: List[Dict[str, Any]] = Field(default_factory=list)
