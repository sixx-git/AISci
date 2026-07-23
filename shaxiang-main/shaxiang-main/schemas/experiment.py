from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class ExperimentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class VariableDefinition(BaseModel):
    """实验变量的定义"""
    name: str = Field(..., description="变量名称")
    type: str = Field(..., description="变量类型: categorical, continuous, ordinal")
    values: list = Field(default_factory=list, description="可选取值范围")
    description: str = Field("", description="变量说明")


class Hypothesis(BaseModel):
    """实验假设"""
    statement: str = Field(..., description="假设陈述")
    rationale: str = Field(..., description="理论依据")
    expected_outcome: str = Field(..., description="预期结果")
    metrics_to_validate: list[str] = Field(default_factory=list, description="验证指标")


class ExperimentPlan(BaseModel):
    """LLM 生成的实验方案（结构化输出）"""
    title: str = Field(..., description="实验标题")
    description: str = Field(..., description="实验描述")
    hypothesis: Hypothesis
    independent_variables: list[VariableDefinition] = Field(default_factory=list)
    dependent_variables: list[VariableDefinition] = Field(default_factory=list)
    control_variables: list[VariableDefinition] = Field(default_factory=list)
    methodology: str = Field(..., description="实验方法描述")
    sample_size: int = Field(10, description="样本/数据量")
    parameters: dict = Field(default_factory=dict, description="实验参数配置")
    # 分析脚本 (用于 sandbox 执行器)
    analysis_script: str = ""
    # 脚本参数
    script_params: dict = Field(default_factory=dict)
    success_criteria: list[str] = Field(default_factory=list, description="成功判定标准")
    risk_assessment: str = Field("", description="风险评估")


class Experiment(BaseModel):
    """实验项目（顶层实体）"""
    id: str
    title: str
    research_goal: str
    hypothesis: str = Field("", description="实验假设（用户输入的核心假设）")
    # 数据集推荐记录（每轮迭代中 LLM 推荐的数据集列表）
    dataset_recommendations: Optional[list] = None
    # 当前轮次的数据配置（用户上传后设置）
    current_data_config: Optional[dict] = None
    # 实验阶段: hypothesis_submitted, data_recommended, data_uploaded, script_designed, executing, analyzing, completed
    phase: str = "created"
    constraints: list[str] = Field(default_factory=list)
    status: ExperimentStatus = ExperimentStatus.CREATED
    executor_type: str = "simulation"
    max_iterations: int = 10
    current_iteration: int = 0
    initial_plan: Optional[ExperimentPlan] = None
    # 数据配置 (用于 sandbox/API 执行器)
    data_config: Optional[dict] = None
    # 人工反馈 (用于 human-in-the-loop)
    human_feedback: Optional[str] = None
    # 反馈状态: none, pending, submitted, applied
    feedback_status: str = "none"
    # 运行模式: smoke_only=小样本验收即完成; full=smoke 后再正式全量/正式样本量推演
    # 空字符串表示跟随全局 EngineConfig.full_dataset_run
    run_mode: str = "smoke_only"
    # 质量模式: draft=有图且非显著问题即通过; strict=需 promising/success
    quality_mode: str = "draft"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
