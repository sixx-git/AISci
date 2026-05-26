"""
Pipeline 相关的 Schema 定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PipelineStatus(str, Enum):
    """Pipeline 状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStage(str, Enum):
    """Pipeline 阶段"""
    PROBLEM_UNDERSTANDING = "problem_understanding"
    LITERATURE_MINING = "literature_mining"
    KNOWLEDGE_GAP = "knowledge_gap"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    HYPOTHESIS_REVIEW = "hypothesis_review"
    EXPERIMENT_DESIGN = "experiment_design"
    SMALL_VALIDATION = "small_validation"
    REPORT_GENERATION = "report_generation"


class PipelineStageStatus(str, Enum):
    """Pipeline 阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRunRequest(BaseModel):
    """Pipeline 运行请求"""
    project_id: str = Field(..., description="项目 ID", example="123e4567-e89b-12d3-a456-426614174000")
    research_question: str = Field(..., description="研究问题", example="如何利用机器学习提高医学影像诊断的准确率？")
    options: Optional[Dict[str, Any]] = Field(default=None, description="可选配置参数")


class PipelineStageLog(BaseModel):
    """Pipeline 阶段日志"""
    stage: PipelineStage = Field(..., description="阶段名称")
    status: PipelineStageStatus = Field(..., description="阶段状态")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长（秒）")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    error_message: Optional[str] = Field(None, description="错误信息")


class PipelineRunResponse(BaseModel):
    """Pipeline 运行响应"""
    pipeline_id: str = Field(..., description="Pipeline 执行 ID")
    project_id: str = Field(..., description="项目 ID")
    status: PipelineStatus = Field(..., description="整体状态")
    stages: List[PipelineStageLog] = Field(default_factory=list, description="各阶段执行日志")
    total_duration: Optional[float] = Field(None, description="总执行时长（秒）")
    final_result: Optional[Dict[str, Any]] = Field(None, description="最终结果")
    created_at: datetime = Field(default_factory=datetime.now)


class PipelineStageExecutionSummary(BaseModel):
    """Pipeline 阶段执行摘要"""
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


class PipelineRunSummary(BaseModel):
    """Pipeline 运行摘要（用于列表）"""
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
    created_at: datetime


class PipelineRunDetail(PipelineRunSummary):
    """Pipeline 运行详情"""
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    stages: List[PipelineStageExecutionSummary]


class PipelineRunResult(BaseModel):
    """Pipeline 完整运行结果"""
    pipeline_id: str = Field(..., description="Pipeline ID")
    run_id: str = Field(..., description="运行 ID")
    project_id: str
    research_question: str
    status: PipelineStatus
    stages: List[PipelineStageLog] = Field(default_factory=list)
    total_duration: Optional[float] = None
    problem_understanding: Optional[Dict[str, Any]] = None
    literature_mining: Optional[Dict[str, Any]] = None
    knowledge_gap: Optional[Dict[str, Any]] = None
    hypothesis_generation: Optional[Dict[str, Any]] = None
    hypothesis_review: Optional[Dict[str, Any]] = None
    experiment_design: Optional[Dict[str, Any]] = None
    small_validation: Optional[Dict[str, Any]] = None
    report_generation: Optional[Dict[str, Any]] = None
    final_report: Optional[Dict[str, Any]] = None
    final_report_id: Optional[str] = Field(None, description="生成的报告 ID")
    failed_stage: Optional[str] = Field(None, description="失败的阶段名称")
    created_at: datetime
    completed_at: Optional[datetime] = None