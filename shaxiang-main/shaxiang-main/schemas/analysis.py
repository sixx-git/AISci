from pydantic import BaseModel, Field


class MetricEvaluation(BaseModel):
    """单个指标评估"""
    metric_name: str
    current_value: float
    previous_value: float | None = None
    change_direction: str = "unchanged"  # improved, declined, unchanged
    change_magnitude: float | None = None


class VisualizationNote(BaseModel):
    """单张可视化图表的简要介绍"""
    chart_name: str = ""
    description: str = ""


class AnalysisReport(BaseModel):
    """LLM 生成的分析报告"""
    iteration_number: int = 0  # 由引擎覆盖写入；模型可不填
    overall_assessment: str = "needs_adjustment"  # promising, needs_adjustment, significant_issue, success
    summary: str = ""
    metric_evaluations: list[MetricEvaluation] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    identified_issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    suggested_adjustments: list[str] = Field(default_factory=list)
    # 对本轮产出图表的简要读图说明（结合文件名、指标与实验目标）
    visualization_notes: list[VisualizationNote] = Field(default_factory=list)
    confidence_level: float = Field(0.5, ge=0.0, le=1.0, description="分析置信度")


class IterationDecision(BaseModel):
    """LLM 生成的迭代决策"""
    should_continue: bool = True
    needs_human_review: bool = False
    review_questions: list[str] = Field(default_factory=list, description="需要人工确认的问题列表")
    next_plan_adjustments: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    new_hypothesis: str | None = None
    expected_improvement: str = ""
    priority_changes: list[str] = Field(default_factory=list)
