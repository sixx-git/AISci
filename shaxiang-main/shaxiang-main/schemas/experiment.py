from pydantic import BaseModel, Field, field_validator, model_validator
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

    @field_validator("statement", "rationale", "expected_outcome", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()


def _pick_alias(data: dict, *names: str) -> Any:
    """按候选名（含大小写变体）取字段。"""
    if not isinstance(data, dict):
        return None
    lower_map = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name in data:
            return data[name]
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _normalize_hypothesis_dict(raw: Any) -> dict:
    if isinstance(raw, str):
        text = raw.strip()
        return {
            "statement": text or "待补充假设陈述",
            "rationale": "待补充理论依据",
            "expected_outcome": "待补充预期结果",
            "metrics_to_validate": [],
        }
    if not isinstance(raw, dict):
        return {
            "statement": "待补充假设陈述",
            "rationale": "待补充理论依据",
            "expected_outcome": "待补充预期结果",
            "metrics_to_validate": [],
        }
    statement = _pick_alias(
        raw, "statement", "Statement", "claim", "Claim", "text", "hypothesis"
    )
    rationale = _pick_alias(
        raw, "rationale", "Rationale", "theory", "Theory", "basis", "Basis"
    )
    expected = _pick_alias(
        raw,
        "expected_outcome",
        "ExpectedOutcome",
        "expected",
        "Expected",
        "outcome",
        "Outcome",
    )
    metrics = _pick_alias(
        raw, "metrics_to_validate", "MetricsToValidate", "metrics", "Metrics"
    )
    if not isinstance(metrics, list):
        metrics = [str(metrics)] if metrics else []
    statement_s = str(statement or "").strip() or "待补充假设陈述"
    return {
        "statement": statement_s,
        "rationale": str(rationale or "").strip() or "待补充理论依据",
        "expected_outcome": str(expected or "").strip() or "待补充预期结果",
        "metrics_to_validate": [str(m) for m in metrics if str(m).strip()],
    }


def normalize_experiment_plan_payload(data: Any) -> Any:
    """兼容 LLM 常见畸形：PascalCase 键、只返回 Hypothesis 嵌套、缺 title/description。"""
    if not isinstance(data, dict):
        return data

    # 单键包装：{"Hypothesis": {...}} / {"experiment_plan": {...}}
    if len(data) == 1:
        only_key = next(iter(data.keys()))
        only_val = data[only_key]
        key_l = str(only_key).lower().replace("-", "_")
        if key_l in {"hypothesis"} and isinstance(only_val, (dict, str)):
            data = {"hypothesis": only_val}
        elif key_l in {"experimentplan", "experiment_plan", "plan", "result", "data"} and isinstance(
            only_val, dict
        ):
            data = dict(only_val)

    out = dict(data)
    # 顶层别名归一
    alias_pairs = [
        ("title", ("title", "Title", "experiment_title", "ExperimentTitle", "name", "Name")),
        (
            "description",
            ("description", "Description", "summary", "Summary", "overview", "Overview"),
        ),
        ("hypothesis", ("hypothesis", "Hypothesis")),
        (
            "methodology",
            ("methodology", "Methodology", "method", "Method", "methods", "Methods"),
        ),
        (
            "independent_variables",
            ("independent_variables", "IndependentVariables", "independentVariables"),
        ),
        (
            "dependent_variables",
            ("dependent_variables", "DependentVariables", "dependentVariables"),
        ),
        (
            "control_variables",
            ("control_variables", "ControlVariables", "controlVariables"),
        ),
        ("parameters", ("parameters", "Parameters", "params", "Params")),
        ("analysis_script", ("analysis_script", "AnalysisScript", "script", "Script")),
        ("script_params", ("script_params", "ScriptParams", "scriptParams")),
        ("success_criteria", ("success_criteria", "SuccessCriteria", "successCriteria")),
        ("risk_assessment", ("risk_assessment", "RiskAssessment", "riskAssessment")),
        ("sample_size", ("sample_size", "SampleSize", "sampleSize")),
    ]
    for canon, aliases in alias_pairs:
        if canon not in out or out.get(canon) in (None, ""):
            picked = _pick_alias(data, *aliases)
            if picked is not None:
                out[canon] = picked

    out["hypothesis"] = _normalize_hypothesis_dict(out.get("hypothesis"))
    hyp_stmt = str((out.get("hypothesis") or {}).get("statement") or "").strip()

    if not str(out.get("title") or "").strip():
        out["title"] = (hyp_stmt[:48] + "…") if len(hyp_stmt) > 48 else (hyp_stmt or "数据分析实验方案")
    if not str(out.get("description") or "").strip():
        out["description"] = hyp_stmt or "基于上传数据的可执行分析方案"
    if not str(out.get("methodology") or "").strip():
        out["methodology"] = "基于绑定数据集的统计分析、指标评估与可视化验证"

    # 列表字段容错
    for list_key in (
        "independent_variables",
        "dependent_variables",
        "control_variables",
        "success_criteria",
    ):
        if list_key not in out or out[list_key] is None:
            out[list_key] = []
        elif not isinstance(out[list_key], list):
            out[list_key] = [out[list_key]]

    if not isinstance(out.get("parameters"), dict):
        out["parameters"] = {}
    if not isinstance(out.get("script_params"), dict):
        out["script_params"] = {}

    return out


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

    @model_validator(mode="before")
    @classmethod
    def _normalize_llm_payload(cls, data: Any) -> Any:
        return normalize_experiment_plan_payload(data)

    @field_validator("title", "description", "methodology", mode="before")
    @classmethod
    def _coerce_required_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()


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
