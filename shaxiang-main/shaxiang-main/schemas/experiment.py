from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional
from enum import Enum
from datetime import datetime
import json
import re


class ExperimentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


_RANGE_IN_PARENS_RE = re.compile(
    r"\(([-+]?\d+(?:\.\d+)?)\s*[-~–—到至]\s*([-+]?\d+(?:\.\d+)?)\)"
)
_BARE_RANGE_RE = re.compile(
    r"^([-+]?\d+(?:\.\d+)?)\s*[-~–—到至]\s*([-+]?\d+(?:\.\d+)?)$"
)


def _coerce_variable_values(v: Any) -> list:
    """LLM 常把 values 写成描述字符串；统一强制为 list，避免 ExperimentPlan 校验失败。"""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, (tuple, set)):
        return list(v)
    if isinstance(v, dict):
        # {"min": 0, "max": 10} / {"values": [...]}
        if isinstance(v.get("values"), list):
            return v["values"]
        if "min" in v and "max" in v:
            try:
                lo, hi = float(v["min"]), float(v["max"])
                if lo.is_integer() and hi.is_integer() and 0 <= hi - lo <= 32:
                    return list(range(int(lo), int(hi) + 1))
                return [v["min"], v["max"]]
            except (TypeError, ValueError):
                pass
        return [v]
    if isinstance(v, (int, float, bool)):
        return [v]
    if not isinstance(v, str):
        return [v]

    s = v.strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    m = _RANGE_IN_PARENS_RE.search(s) or _BARE_RANGE_RE.match(s)
    if m:
        try:
            lo_f, hi_f = float(m.group(1)), float(m.group(2))
            if lo_f.is_integer() and hi_f.is_integer():
                lo, hi = int(lo_f), int(hi_f)
                if lo > hi:
                    lo, hi = hi, lo
                # 小范围展开；大范围只保留端点，避免撑爆 schema
                if hi - lo <= 32:
                    return list(range(lo, hi + 1))
                return [lo, hi]
            return [lo_f, hi_f]
        except (TypeError, ValueError):
            pass

    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if parts:
            return parts
    return [s]


class VariableDefinition(BaseModel):
    """实验变量的定义"""
    name: str = Field(..., description="变量名称")
    type: str = Field(..., description="变量类型: categorical, continuous, ordinal")
    values: list = Field(
        default_factory=list,
        description="可选取值范围，必须是 JSON 数组，例如 [0,1,2] 或 [\"A\",\"B\"]，禁止写成描述字符串",
    )
    description: str = Field("", description="变量说明")

    @field_validator("values", mode="before")
    @classmethod
    def _normalize_values(cls, v: Any) -> list:
        return _coerce_variable_values(v)


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
