"""人在回路相关 Schema"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class StageHumanEditRequest(BaseModel):
    project_id: str
    run_id: str
    stage: str
    output_data: Dict[str, Any]
    human_feedback: str = ""
    mark_reviewed: bool = True


class StageHumanEditResponse(BaseModel):
    run_id: str
    stage: str
    human_modified_output: Optional[Dict[str, Any]] = None
    human_reviewed: bool = False
    human_feedback: Optional[str] = None
    edited_at: Optional[str] = None
    revision_history: List[Dict[str, Any]] = Field(default_factory=list)


class RerunFromStageRequest(BaseModel):
    project_id: str
    run_id: str
    stage: str
    use_human_modified_output: bool = True


class RerunFromStageResponse(BaseModel):
    run_id: str
    parent_run_id: str
    rerun_from_stage: str
    status: str


class PromptOverrideRequest(BaseModel):
    project_id: str = Field(..., description="项目 ID")
    prompt_template: str = Field(..., description="覆盖后的 Prompt 模板")


class PromptInfoResponse(BaseModel):
    project_id: str
    stage: str
    template_name: str
    default_template: str
    override_template: Optional[str] = None
    effective_template: str
    has_override: bool
    updated_at: Optional[str] = None


class StageChatRequest(BaseModel):
    project_id: str
    run_id: str
    stage: str
    message: str
    apply_change: bool = True


class StageChatResponse(BaseModel):
    run_id: str
    stage: str
    user_message: str
    revised_output: Dict[str, Any]
    explanation: str
    changes_summary: List[str] = Field(default_factory=list)
    applied: bool = True


class MentorReviewRequest(BaseModel):
    project_id: str
    run_id: Optional[str] = None
    target_type: str = Field(..., description="hypothesis | experiment_design | report")
    stage: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    research_question: str = ""
    user_notes: str = ""


class MentorReviewResponse(BaseModel):
    target_type: str
    review: Dict[str, Any]


class ReportReviseRequest(BaseModel):
    project_id: str
    report_id: str
    message: str
    apply_change: bool = True
