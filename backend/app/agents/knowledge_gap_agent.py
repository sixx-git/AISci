"""
知识缺口智能体 (KnowledgeGapAgent)
"""
import logging
from typing import Optional, List
from pydantic import BaseModel, Field

from app.agents.literature_mining_agent import ScienceFact
from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class KnownFactSummary(BaseModel):
    """已知事实摘要"""
    fact_id: str = Field(..., description="事实ID")
    content: str = Field(..., description="事实内容")
    source_paper_title: Optional[str] = Field(None, description="来源论文标题")


class KnowledgeGapItem(BaseModel):
    """知识缺口项"""
    gap_id: str = Field(..., description="缺口ID")
    description: str = Field(..., description="缺口描述")
    basis: List[str] = Field(..., description="依据（引用相关事实ID）")
    potential_value: str = Field(..., description="可能的研究价值")


class ContradictionItem(BaseModel):
    """矛盾项"""
    contradiction_id: str = Field(..., description="矛盾ID")
    fact_ids: List[str] = Field(..., description="涉及的事实ID列表")
    description: str = Field(..., description="矛盾描述")


class PossibleConnectionItem(BaseModel):
    """可能的联系项"""
    connection_id: str = Field(..., description="联系ID")
    fact_ids: List[str] = Field(..., description="涉及的事实ID列表")
    description: str = Field(..., description="联系描述")
    confidence: float = Field(..., ge=0, le=1, description="置信度")


class ResearchOpportunityItem(BaseModel):
    """研究机会项"""
    opportunity_id: str = Field(..., description="机会ID")
    title: str = Field(..., description="研究机会标题")
    description: str = Field(..., description="描述")
    related_gap_ids: List[str] = Field(..., description="相关的知识缺口ID")
    expected_impact: str = Field(..., description="预期影响")
    feasibility: float = Field(..., ge=0, le=1, description="可行性评分")


class KnowledgeGapRequest(BaseModel):
    """知识缺口分析请求"""
    facts: List[ScienceFact] = Field(..., description="科学事实列表")
    uncertain_points: List[str] = Field(..., description="不确定的点列表")


class KnowledgeGapResponse(BaseModel):
    """知识缺口分析响应"""
    known_facts: List[KnownFactSummary] = Field(..., description="已知事实摘要")
    knowledge_gaps: List[KnowledgeGapItem] = Field(..., description="知识缺口列表")
    contradictions: List[ContradictionItem] = Field(..., description="矛盾列表")
    possible_connections: List[PossibleConnectionItem] = Field(..., description="可能的联系列表")
    research_opportunities: List[ResearchOpportunityItem] = Field(..., description="研究机会列表")


class KnowledgeGapAgent:
    """知识缺口智能体"""
    
    def __init__(self):
        pass
    
    def analyze(
        self,
        facts: List[ScienceFact],
        uncertain_points: List[str],
        *,
        research_question: str = "",
        main_contradiction: str = "",
        expected_output_summary: str = "",
    ) -> KnowledgeGapResponse:
        """
        分析知识缺口
        
        Args:
            facts: 科学事实列表
            uncertain_points: 不确定的点列表
            research_question: 用户研究问题（缺口锚点）
            main_contradiction: 问题理解中的主要矛盾
            expected_output_summary: 问题理解中的期望输出摘要
            
        Returns:
            KnowledgeGapResponse: 分析结果
        """
        try:
            formatted_facts = self._format_facts(facts)
            formatted_uncertain = self._format_uncertain(uncertain_points)
            
            logger.info(f"开始分析知识缺口，共 {len(facts)} 个事实")
            result = self._analyze_knowledge_gaps(
                formatted_facts,
                formatted_uncertain,
                research_question=(research_question or "").strip(),
                main_contradiction=(main_contradiction or "").strip(),
                expected_output_summary=(expected_output_summary or "").strip(),
            )
            
            # 验证并标准化结果
            response = self._validate_and_normalize(result, facts)
            
            logger.info(f"成功分析知识缺口: {len(response.knowledge_gaps)} 个缺口")
            
            return response
            
        except Exception as e:
            logger.error(f"分析知识缺口时出错: {e}", exc_info=True)
            raise
    
    def _format_facts(self, facts: List[ScienceFact]) -> str:
        """
        格式化科学事实
        
        Args:
            facts: 科学事实列表
            
        Returns:
            格式化后的字符串
        """
        if not facts:
            return "（无事实）"
        
        facts_text = []
        
        for fact in facts:
            # 兼容 dict 和 object
            if isinstance(fact, dict):
                source_title = fact.get("source_paper_title", fact.get("source", ""))
                fact_id = fact.get("fact_id", fact.get("id", ""))
                content = fact.get("content", fact.get("fact", str(fact)))
                chunk_id = str(fact.get("source_chunk_id") or fact.get("chunk_id") or "")
            else:
                source_title = getattr(fact, "source_paper_title", "")
                fact_id = getattr(fact, "fact_id", "")
                content = getattr(fact, "content", str(fact))
                chunk_id = str(getattr(fact, "source_chunk_id", "") or "")
            source_info = f" (来源: {source_title})" if source_title else ""
            quality = ""
            if str(fact_id).startswith("paper_fact_") or chunk_id.startswith("paper_"):
                quality = " [摘要级代理事实，非全文 chunk]"
            fact_text = f"[{fact_id}] {content}{source_info}{quality}"
            facts_text.append(fact_text)
        
        return "\n\n".join(facts_text)
    
    def _format_uncertain(self, uncertain_points: List[str]) -> str:
        """
        格式化不确定的点
        
        Args:
            uncertain_points: 不确定的点列表
            
        Returns:
            格式化后的字符串
        """
        if not uncertain_points:
            return "（无不确定点）"
        
        return "\n".join([f"- {point}" for point in uncertain_points])
    
    def _analyze_knowledge_gaps(
        self,
        formatted_facts: str,
        formatted_uncertain: str,
        *,
        research_question: str = "",
        main_contradiction: str = "",
        expected_output_summary: str = "",
    ) -> dict:
        """调用 Qwen 分析知识缺口。"""
        prompt_loader = get_prompt_loader()
        
        prompt = prompt_loader.render_template(
            "knowledge_gap",
            {
                "facts_list": formatted_facts,
                "uncertain_list": formatted_uncertain,
                "research_question": research_question or "（未提供）",
                "main_contradiction": main_contradiction or "（未提供）",
                "expected_output_summary": expected_output_summary or "（未提供）",
            }
        )

        # 定义 schema 示例
        schema_example = {
            "known_facts": [
                {
                    "fact_id": "fact_001",
                    "content": "事实内容",
                    "source_paper_title": "来源论文标题"
                }
            ],
            "knowledge_gaps": [
                {
                    "gap_id": "gap_001",
                    "description": "缺口描述",
                    "basis": ["fact_001"],
                    "potential_value": "可能的研究价值"
                }
            ],
            "contradictions": [
                {
                    "contradiction_id": "contradict_001",
                    "fact_ids": ["fact_001", "fact_002"],
                    "description": "矛盾描述"
                }
            ],
            "possible_connections": [
                {
                    "connection_id": "connect_001",
                    "fact_ids": ["fact_001", "fact_002"],
                    "description": "联系描述",
                    "confidence": 0.7
                }
            ],
            "research_opportunities": [
                {
                    "opportunity_id": "opp_001",
                    "title": "研究机会标题",
                    "description": "详细描述",
                    "related_gap_ids": ["gap_001"],
                    "expected_impact": "预期影响",
                    "feasibility": 0.8
                }
            ]
        }

        # 调用 Qwen
        return qwen_structured_chat(
            prompt=prompt,
            schema_example=schema_example,
            prompt_version="knowledge_gap"
        )
    
    def _validate_and_normalize(
        self,
        result: dict,
        facts: List[ScienceFact]
    ) -> KnowledgeGapResponse:
        """
        验证并标准化结果
        
        Args:
            result: LLM 返回的字典
            facts: 原始事实列表
            
        Returns:
            KnowledgeGapResponse: 验证后的响应
        """
        # 确保必要字段存在
        for field in ["known_facts", "knowledge_gaps", "contradictions", "possible_connections", "research_opportunities"]:
            if field not in result:
                result[field] = []
        
        # 验证知识缺口的依据
        valid_gaps = []
        for gap in result.get("knowledge_gaps", []):
            if not gap.get("basis"):
                gap["basis"] = []
            valid_gaps.append(gap)
        
        result["knowledge_gaps"] = valid_gaps
        
        # 确保 confidence 是数值
        for connection in result.get("possible_connections", []):
            if not isinstance(connection.get("confidence"), (int, float)):
                connection["confidence"] = 0.5
        
        for opportunity in result.get("research_opportunities", []):
            if not isinstance(opportunity.get("feasibility"), (int, float)):
                opportunity["feasibility"] = 0.5
        
        # 使用 Pydantic 验证
        return KnowledgeGapResponse(**result)
    
    def _empty_response(self) -> KnowledgeGapResponse:
        """
        返回空响应
        
        Returns:
            KnowledgeGapResponse: 空响应
        """
        return KnowledgeGapResponse(
            known_facts=[],
            knowledge_gaps=[],
            contradictions=[],
            possible_connections=[],
            research_opportunities=[]
        )


# 全局单例
_agent_instance: Optional[KnowledgeGapAgent] = None


def get_knowledge_gap_agent() -> KnowledgeGapAgent:
    """获取 KnowledgeGapAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = KnowledgeGapAgent()
    return _agent_instance
