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
