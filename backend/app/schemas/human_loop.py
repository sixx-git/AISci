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
    rerun_mode: str = Field(
        default="single_stage",
        description="single_stage=仅重跑本阶段; from_stage_onward=从本阶段起执行后续流程",
    )
    human_feedback: str = Field(
        default="",
        description="重跑时注入该阶段的额外约束/修改意见",
    )


class RerunFromStageResponse(BaseModel):
    run_id: str
    parent_run_id: str
    rerun_from_stage: str
    rerun_mode: str = "single_stage"
    status: str
    in_place: bool = Field(default=False, description="single_stage 时为 True，表示未创建新 run")


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


class PromptPresetVariantInfo(BaseModel):
    id: str
    label: str
    file: str
    description: Optional[str] = None


class PromptPresetPackInfo(BaseModel):
    id: str
    label: str
    description: str = ""
    reference: Optional[str] = None
    recommended_pipeline_mode: Optional[str] = None
    requires_federated: bool = False
    stages: Dict[str, List[PromptPresetVariantInfo]] = Field(default_factory=dict)


class PromptPresetCatalogResponse(BaseModel):
    version: int = 1
    excluded_stages: List[str] = Field(default_factory=list)
    excluded_reason: str = ""
    packs: List[PromptPresetPackInfo] = Field(default_factory=list)
    default_pack_id: str = "pack_c"


class PromptPresetContentResponse(BaseModel):
    pack_id: str
    pack_label: Optional[str] = None
    stage: str
    variant_id: str
    variant_label: Optional[str] = None
    description: Optional[str] = None
    content: str


class PromptPresetApplyRequest(BaseModel):
    project_id: str
    pack_id: str
    stage: Optional[str] = None
    variant_id: Optional[str] = None
    apply_all_stages: bool = False


class PromptPresetApplyResponse(BaseModel):
    project_id: str
    pack_id: str
    variant_id: Optional[str] = None
    applied: List[Dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class StageChatRequest(BaseModel):
    project_id: str
    run_id: str
    stage: str
    message: str
    apply_change: bool = True
    mode: str = Field(
        default="advisory",
        description="advisory=咨询对话不改输出; revise=轻量修订 human_modified_output",
    )


class StageChatResponse(BaseModel):
    run_id: str
    stage: str
    user_message: str
    revised_output: Dict[str, Any]
    explanation: str
    changes_summary: List[str] = Field(default_factory=list)
    applied: bool = True
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    revision_mode: Optional[str] = None
    mode: Optional[str] = None


class MentorReviewRequest(BaseModel):
    project_id: str
    run_id: Optional[str] = None
    report_id: Optional[str] = None
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
    section_keys: List[str] = Field(default_factory=list, description="局部修订的章节字段，空则整份报告")


class HitlGateResumeRequest(BaseModel):
    run_id: str
    project_id: str
    action: str = Field(..., description="continue | rerun | abort")
    human_feedback: str = ""
    inject_feedback: bool = True


class HitlGateStatusResponse(BaseModel):
    run_id: str
    project_id: Optional[str] = None
    status: str
    paused: bool = False
    stage: Optional[str] = None
    stage_label: Optional[str] = None
    resume_phase: Optional[str] = None
    paused_at: Optional[str] = None
    cleared_stages: List[str] = Field(default_factory=list)


class HitlGateResumeResponse(BaseModel):
    action: str
    status: str
    run_id: str
    rerun_from_stage: Optional[str] = None
    feedback_constraints_count: Optional[int] = None
