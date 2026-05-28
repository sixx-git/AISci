"""
Pipeline 相关数据模型
包含：PipelineRun, PipelineStageExecution, PromptVersion
"""
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from datetime import datetime
import uuid

from app.models.core import Base


class PipelineStatus(str, Enum):
    """Pipeline 运行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class PipelineStage(str, Enum):
    """Pipeline 阶段枚举"""
    PROBLEM_UNDERSTANDING = "problem_understanding"
    LITERATURE_MINING = "literature_mining"
    KNOWLEDGE_GAP = "knowledge_gap"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    HYPOTHESIS_REVIEW = "hypothesis_review"
    EXPERIMENT_DESIGN = "experiment_design"
    SMALL_VALIDATION = "small_validation"
    REPORT_GENERATION = "report_generation"


class PipelineRun(Base):
    """
    Pipeline 运行记录表
    存储每次 Pipeline 运行的完整信息
    """
    __tablename__ = "pipeline_runs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True, comment="Pipeline Run ID")
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True, comment="关联项目ID")
    
    # 运行基本信息
    run_id = Column(String(36), nullable=False, unique=True, index=True, comment="运行ID（用于引用）")
    research_question = Column(Text, nullable=False, comment="研究问题")
    status = Column(SQLEnum(PipelineStatus), default=PipelineStatus.PENDING, nullable=False, index=True, comment="运行状态")
    
    # 时间信息
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    total_duration_ms = Column(Integer, nullable=True, comment="总耗时（毫秒）")
    
    # 输入和配置
    input_data = Column(JSON, nullable=True, comment="输入数据（JSON）")
    config = Column(JSON, nullable=True, comment="运行配置（JSON）")
    prompt_versions_used = Column(JSON, nullable=True, comment="使用的Prompt版本信息（JSON）")
    
    # 输出和结果
    output_data = Column(JSON, nullable=True, comment="输出数据（JSON）")
    final_report_id = Column(String(36), ForeignKey("reports.id"), nullable=True, index=True, comment="关联报告ID")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_stacktrace = Column(Text, nullable=True, comment="错误堆栈")
    failed_stage = Column(SQLEnum(PipelineStage), nullable=True, comment="失败的阶段")
    
    # 版本信息
    version = Column(Integer, default=1, comment="运行版本号")
    model_versions = Column(JSON, nullable=True, comment="使用的模型版本信息（JSON）")
    software_version = Column(String(100), nullable=True, comment="软件版本号")
    
    # 标签和元数据
    tags = Column(Text, nullable=True, comment="标签，逗号分隔")
    notes = Column(Text, nullable=True, comment="备注")
    extra_metadata = Column(JSON, nullable=True, comment="额外元数据（JSON）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    project = relationship("Project")
    report = relationship("Report")
    stage_executions = relationship("PipelineStageExecution", back_populates="pipeline_run", cascade="all, delete-orphan")
    
    __table_args__ = {'comment': 'Pipeline 运行记录表'}


class PipelineStageExecution(Base):
    """
    Pipeline 阶段执行表
    存储每个阶段的详细执行信息
    """
    __tablename__ = "pipeline_stage_executions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True, comment="阶段执行ID")
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id"), nullable=False, index=True, comment="关联运行ID")
    
    # 阶段信息
    stage = Column(SQLEnum(PipelineStage), nullable=False, index=True, comment="阶段名称")
    stage_order = Column(Integer, nullable=False, comment="阶段序号（1-8）")
    status = Column(SQLEnum(PipelineStatus), default=PipelineStatus.PENDING, nullable=False, index=True, comment="执行状态")
    
    # 时间信息
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    duration_ms = Column(Integer, nullable=True, comment="耗时（毫秒）")
    
    # 输入输出
    input_data = Column(JSON, nullable=True, comment="输入数据（JSON）")
    output_data = Column(JSON, nullable=True, comment="输出数据（JSON）")
    
    # 模型和Prompt
    model_used = Column(String(100), nullable=True, comment="使用的模型")
    model_parameters = Column(JSON, nullable=True, comment="模型参数（JSON）")
    prompt_used = Column(Text, nullable=True, comment="使用的Prompt")
    prompt_version_id = Column(String(36), ForeignKey("prompt_versions.id"), nullable=True, index=True, comment="关联Prompt版本ID")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_stacktrace = Column(Text, nullable=True, comment="错误堆栈")
    
    # 资源使用
    token_count = Column(Integer, nullable=True, comment="Token 数量")
    cost_estimate = Column(Float, nullable=True, comment="预估成本（USD）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 关系
    pipeline_run = relationship("PipelineRun", back_populates="stage_executions")
    prompt_version = relationship("PromptVersion")
    
    __table_args__ = {'comment': 'Pipeline 阶段执行表'}


class PromptStatus(str, Enum):
    """Prompt 版本状态枚举"""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PromptVersion(Base):
    """
    Prompt 版本表
    存储不同阶段使用的 Prompt 版本
    """
    __tablename__ = "prompt_versions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True, comment="Prompt 版本ID")
    
    # Prompt 基本信息
    name = Column(String(200), nullable=False, index=True, comment="Prompt 名称")
    stage = Column(SQLEnum(PipelineStage), nullable=False, index=True, comment="适用阶段")
    version = Column(Integer, default=1, nullable=False, comment="版本号")
    
    # Prompt 内容
    prompt_template = Column(Text, nullable=False, comment="Prompt 模板")
    variables = Column(JSON, nullable=True, comment="变量列表（JSON）")
    
    # 元数据
    description = Column(Text, nullable=True, comment="描述")
    creator = Column(String(100), nullable=True, comment="创建者")
    status = Column(SQLEnum(PromptStatus), default=PromptStatus.ACTIVE, nullable=False, index=True, comment="状态")
    
    # 性能数据
    avg_token_count = Column(Integer, nullable=True, comment="平均 Token 数量")
    avg_execution_time_ms = Column(Integer, nullable=True, comment="平均执行时间（毫秒）")
    success_rate = Column(Float, nullable=True, comment="成功率（0-1）")
    
    # 配置
    model = Column(String(100), nullable=True, comment="默认使用的模型")
    default_parameters = Column(JSON, nullable=True, comment="默认参数（JSON）")
    
    # 版本历史
    parent_version_id = Column(String(36), nullable=True, index=True, comment="父版本ID")
    change_log = Column(Text, nullable=True, comment="变更日志")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    __table_args__ = {'comment': 'Prompt 版本表'}
