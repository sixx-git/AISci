"""
研究相关 Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class HypothesisCreate(BaseModel):
    """创建假设"""
    project_id: str = Field(..., description="项目ID")
    research_question: str = Field(..., description="研究问题")
    hypothesis: str = Field(..., description="假设内容")
    rationale: str = Field(..., description="理论依据")
    novelty: str = Field(..., description="创新性")
    testability: str = Field(..., description="可测试性")
    required_data: str = Field(..., description="所需数据")
    possible_method: str = Field(..., description="可能的方法")
    risk: str = Field(..., description="风险")
    status: Optional[str] = Field("draft", description="状态")
    priority: Optional[int] = Field(3, ge=1, le=5, description="优先级 1-5")
    confidence: Optional[float] = Field(0.5, ge=0, le=1, description="置信度 0-1")


class HypothesisResponse(HypothesisCreate):
    """假设响应"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class HypothesisItem(BaseModel):
    """单个假设项（用于生成结果）"""
    hypothesis: str = Field(..., description="假设内容")
    rationale: str = Field(..., description="理论依据")
    novelty: str = Field(..., description="创新性")
    testability: str = Field(..., description="可测试性")
    required_data: str = Field(..., description="所需数据")
    possible_method: str = Field(..., description="可能的方法")
    risk: str = Field(..., description="风险")


class HypothesisGenerationRequest(BaseModel):
    """假设生成请求"""
    project_id: str = Field(..., description="项目ID")
    research_question: str = Field(..., description="研究问题")
    facts: List[dict] = Field(..., description="事实列表")
    knowledge_gaps: List[dict] = Field(..., description="知识缺口列表")
    constraints: List[str] = Field(..., description="约束条件列表")


class HypothesisGenerationResponse(BaseModel):
    """假设生成响应"""
    hypotheses: List[HypothesisItem] = Field(..., description="生成的假设列表")
    summary: Optional[str] = Field(None, description="生成摘要")


class ExperimentDesignCreate(BaseModel):
    """创建实验设计"""
    project_id: str = Field(..., description="项目ID")
    hypothesis_id: str = Field(..., description="假设ID")
    hypothesis: str = Field(..., description="假设内容")
    methods: str = Field(..., description="研究方法")
    datasets: str = Field(..., description="数据集")
    source_data: str = Field(..., description="源数据")
    target_data: str = Field(..., description="目标数据")
    baselines: str = Field(..., description="基线方法")
    metrics: str = Field(..., description="评估指标")
    experimental_steps: str = Field(..., description="实验步骤")
    expected_results: str = Field(..., description="预期结果")
    limitations: str = Field(..., description="局限性")
    status: Optional[str] = Field("draft", description="状态")
    priority: Optional[int] = Field(3, ge=1, le=5, description="优先级 1-5")


class ExperimentDesignDBResponse(ExperimentDesignCreate):
    """实验设计数据库响应"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ExperimentDesignItem(BaseModel):
    """单个实验设计项（用于生成结果）"""
    methods: str = Field(..., description="研究方法")
    datasets: str = Field(..., description="数据集")
    source_data: str = Field(..., description="源数据")
    target_data: str = Field(..., description="目标数据")
    baselines: str = Field(..., description="基线方法")
    metrics: str = Field(..., description="评估指标")
    experimental_steps: str = Field(..., description="实验步骤")
    expected_results: str = Field(..., description="预期结果")
    limitations: str = Field(..., description="局限性")


class ExperimentDesignRequest(BaseModel):
    """实验设计请求"""
    project_id: str = Field(..., description="项目ID")
    hypothesis_id: str = Field(..., description="假设ID")
    hypothesis: str = Field(..., description="假设内容")
    rationale: Optional[str] = Field(None, description="理论依据")
    novelty: Optional[str] = Field(None, description="创新性")
    testability: Optional[str] = Field(None, description="可测试性")
    required_data: Optional[str] = Field(None, description="所需数据")
    possible_method: Optional[str] = Field(None, description="可能的方法")
    risk: Optional[str] = Field(None, description="风险")


class ExperimentDesignGenerationResponse(BaseModel):
    """实验设计生成响应"""
    experiment_design: ExperimentDesignItem = Field(..., description="生成的实验设计")
    summary: Optional[str] = Field(None, description="生成摘要")
