"""
Pipeline ??? Schema ??
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PipelineStatus(str, Enum):
    """Pipeline ??"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    PAUSED = "paused"


class PipelineStage(str, Enum):
    """Pipeline ??"""
    PROBLEM_UNDERSTANDING = "problem_understanding"
    LITERATURE_MINING = "literature_mining"
    DATA_ACQUISITION = "data_acquisition"
    KNOWLEDGE_GAP = "knowledge_gap"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    HYPOTHESIS_REVIEW = "hypothesis_review"
    EXPERIMENT_DESIGN = "experiment_design"  # legacy
    SMALL_VALIDATION = "small_validation"  # legacy
    ITERATIVE_EXPERIMENT = "iterative_experiment"
    REPORT_GENERATION = "report_generation"


class PipelineStageStatus(str, Enum):
    """Pipeline ????"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class PipelineRunRequest(BaseModel):
    """Pipeline ????"""
    project_id: str = Field(..., description="?? ID", example="123e4567-e89b-12d3-a456-426614174000")
    research_question: str = Field(..., description="????", example="?????????????????????")
    options: Optional[Dict[str, Any]] = Field(default=None, description="??????")


class PipelineStageLog(BaseModel):
    """Pipeline ????"""
    stage: PipelineStage = Field(..., description="????")
    status: PipelineStageStatus = Field(..., description="????")
    start_time: Optional[datetime] = Field(None, description="????")
    end_time: Optional[datetime] = Field(None, description="????")
    duration: Optional[float] = Field(None, description="???????")
    input_data: Optional[Dict[str, Any]] = Field(None, description="????")
    output_data: Optional[Dict[str, Any]] = Field(None, description="????")
    error_message: Optional[str] = Field(None, description="????")
    model_used: Optional[str] = Field(None, description="???????")
    token_count: Optional[int] = Field(None, description="Token ???")
    prompt_used: Optional[str] = Field(None, description="??????")
    model_parameters: Optional[Dict[str, Any]] = Field(None, description="????")
    human_modified_output: Optional[Dict[str, Any]] = Field(None, description="????????")
    human_reviewed: bool = Field(False, description="???????")
    human_feedback: Optional[str] = Field(None, description="??????")
    edited_at: Optional[str] = Field(None, description="??????")
    revision_history: Optional[List[Dict[str, Any]]] = Field(None, description="????")


class PipelineRunResponse(BaseModel):
    """Pipeline ????"""
    pipeline_id: str = Field(..., description="Pipeline ?? ID")
    project_id: str = Field(..., description="?? ID")
    status: PipelineStatus = Field(..., description="????")
    stages: List[PipelineStageLog] = Field(default_factory=list, description="???????")
    total_duration: Optional[float] = Field(None, description="????????")
    final_result: Optional[Dict[str, Any]] = Field(None, description="????")
    created_at: datetime = Field(default_factory=datetime.now)


class PipelineStageExecutionSummary(BaseModel):
    """Pipeline ??????"""
    id: str
    pipeline_run_id: str
    stage: str
    stage_order: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    token_count: Optional[int]
    model_used: Optional[str] = None
    prompt_used: Optional[str] = None
    model_parameters: Optional[Dict[str, Any]] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    human_modified_output: Optional[Dict[str, Any]] = None
    human_reviewed: bool = False
    human_feedback: Optional[str] = None
    edited_at: Optional[str] = None
    revision_history: Optional[List[Dict[str, Any]]] = None


class PipelineRunSummary(BaseModel):
    """Pipeline ??????????"""
    id: str
    run_id: str
    project_id: str
    research_question: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_duration_ms: Optional[int]
    final_report_id: Optional[str]
    failed_stage: Optional[str]
    current_stage: Optional[str] = None
    created_at: datetime
    extra_metadata: Optional[Dict[str, Any]] = None


class PipelineRunDetail(PipelineRunSummary):
    """Pipeline ????"""
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    stages: List[PipelineStageExecutionSummary]


class PipelineRunResult(BaseModel):
    """Pipeline ??????"""
    pipeline_id: str = Field(..., description="Pipeline ID")
    run_id: str = Field(..., description="?? ID")
    project_id: str
    research_question: str
    status: PipelineStatus
    stages: List[PipelineStageLog] = Field(default_factory=list)
    total_duration: Optional[float] = None
    error_message: Optional[str] = Field(None, description="????")
    problem_understanding: Optional[Dict[str, Any]] = None
    literature_mining: Optional[Dict[str, Any]] = None
    knowledge_gap: Optional[Dict[str, Any]] = None
    hypothesis_generation: Optional[Dict[str, Any]] = None
    hypothesis_review: Optional[Dict[str, Any]] = None
    iterative_experiment: Optional[Dict[str, Any]] = None
    experiment_design: Optional[Dict[str, Any]] = None  # legacy / ????
    small_validation: Optional[Dict[str, Any]] = None  # legacy / ????
    report_generation: Optional[Dict[str, Any]] = None
    final_report: Optional[Dict[str, Any]] = None
    final_report_id: Optional[str] = Field(None, description="????? ID")
    failed_stage: Optional[str] = Field(None, description="???????")
    current_stage: Optional[str] = Field(None, description="?????? key")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="?????????")
    created_at: datetime
    completed_at: Optional[datetime] = None


class LoopDryRunRequest(BaseModel):
    """Loop ?? Dry-run ????? LLM?"""
    run_options: Optional[Dict[str, Any]] = Field(default=None, description="? Pipeline run options ??")
    quality_trend: Optional[List[Dict[str, Any]]] = Field(default=None, description="????? Gate ??")
    round_num: int = Field(default=2, ge=1, le=5, description="Discovery ??")
    hypothesis_review: Optional[Dict[str, Any]] = Field(default=None, description="????? Accept ??")
    small_validation: Optional[Dict[str, Any]] = Field(default=None)
    project_mode: str = Field(default="general", description="general | federated_learning")


class EvidenceIterationDecisionRequest(BaseModel):
    """?????????"""
    project_id: str = Field(..., description="?? ID")
    hint_id: str = Field(..., description="????? ID")
    decision: str = Field(..., description="approve=????; reject=?????")


class EvidenceIterationDecisionResponse(BaseModel):
    """?????????"""
    run_id: str
    parent_run_id: Optional[str] = None
    decision: str
    status: str
    rerun_from_stage: Optional[str] = None
    rerun_mode: Optional[str] = None


class PipelinePauseResponse(BaseModel):
    """User pause request ack (cooperative: takes effect after current stage)."""
    run_id: str
    accepted: bool = True
    already_requested: bool = False
    status: str = "running"
    message: str = ""


class PipelineResumeResponse(BaseModel):
    """Resume after user pause."""
    run_id: str
    status: str = "running"
    resume_phase: Optional[str] = None
    message: str = ""
