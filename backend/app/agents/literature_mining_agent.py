"""
文献挖掘智能体 (LiteratureMiningAgent)
"""
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.vector_store import (
    search_vector_store,
    SearchResult
)
from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)


class ScienceFact(BaseModel):
    """科学事实"""
    fact_id: str = Field(..., description="事实ID")
    content: str = Field(..., description="事实内容")
    source_chunk_id: str = Field(..., description="来源Chunk ID")
    source_paper_title: Optional[str] = Field(None, description="来源论文标题")
    source_page: Optional[int] = Field(None, description="来源页码")


class EvidenceItem(BaseModel):
    """证据项"""
    evidence_id: str = Field(..., description="证据ID")
    fact_id: str = Field(..., description="关联的事实ID")
    text: str = Field(..., description="证据原文")
    source_chunk_id: str = Field(..., description="来源Chunk ID")


class CitationMapItem(BaseModel):
    """引用映射项"""
    paper_title: str = Field(..., description="论文标题")
    fact_ids: List[str] = Field(..., description="引用的事实ID列表")
    chunk_ids: List[str] = Field(..., description="涉及的Chunk ID列表")


class LiteratureMiningRequest(BaseModel):
    """文献挖掘请求"""
    project_id: str = Field(..., description="项目ID", example="project-123")
    research_question: str = Field(..., description="研究问题", example="机器学习在医学影像中的应用效果如何？")
    top_k: int = Field(10, ge=1, le=30, description="检索的文献片段数量", example=10)


class LiteratureMiningResponse(BaseModel):
    """文献挖掘响应"""
    facts: List[ScienceFact] = Field(..., description="关键科学事实列表")
    evidence: List[EvidenceItem] = Field(..., description="证据列表")
    source_papers: List[str] = Field(..., description="来源论文标题列表")
    citation_map: List[CitationMapItem] = Field(..., description="引用映射")
    uncertain_points: List[str] = Field(..., description="不确定的点")


# Prompt 模板
LITERATURE_MINING_PROMPT_TEMPLATE = """你是一位专业的文献分析专家，擅长从学术文献中提取关键科学事实。

## 任务要求
基于提供的文献片段，提取与研究问题相关的关键科学事实。

## 重要原则
1. 每条事实必须绑定来源信息：chunk_id、论文标题、页码
2. 禁止编造无来源的事实
3. 仅基于提供的文献片段进行分析
4. 标注不确定或有争议的观点
5. 保持事实的客观性，避免主观推断

## 输入信息
研究问题：{research_question}

文献片段：
{literature_chunks}

## 输出格式要求
请严格按照以下 JSON 格式输出，不要添加额外解释或 markdown 标记：
{{
  "facts": [
    {{
      "fact_id": "fact_001",
      "content": "事实内容",
      "source_chunk_id": "chunk_id",
      "source_paper_title": "论文标题",
      "source_page": 页码
    }}
  ],
  "evidence": [
    {{
      "evidence_id": "ev_001",
      "fact_id": "fact_001",
      "text": "证据原文",
      "source_chunk_id": "chunk_id"
    }}
  ],
  "source_papers": ["论文标题1", "论文标题2"],
  "citation_map": [
    {{
      "paper_title": "论文标题",
      "fact_ids": ["fact_001"],
      "chunk_ids": ["chunk_id"]
    }}
  ],
  "uncertain_points": ["不确定的点1", "不确定的点2"]
}}"""


class LiteratureMiningAgent:
    """文献挖掘智能体"""
    
    def __init__(self):
        pass
    
    def mine(
        self,
        project_id: str,
        research_question: str,
        top_k: int = 10
    ) -> LiteratureMiningResponse:
        """
        挖掘文献
        
        Args:
            project_id: 项目ID
            research_question: 研究问题
            top_k: 检索的文献片段数量
            
        Returns:
            LiteratureMiningResponse: 挖掘结果
        """
        try:
            # 1. 调用 FAISS 检索相关文献片段
            logger.info(f"开始检索文献片段: project_id={project_id}, top_k={top_k}")
            search_results = search_vector_store(
                project_id=project_id,
                query=research_question,
                top_k=top_k
            )
            
            if not search_results:
                logger.warning(f"未找到相关文献片段")
                return self._empty_response()
            
            # 2. 格式化文献片段
            formatted_chunks = self._format_chunks(search_results)
            
            # 3. 调用 Qwen 提取关键科学事实
            logger.info(f"开始提取科学事实，共 {len(search_results)} 个片段")
            result = self._extract_facts(research_question, formatted_chunks)
            
            # 4. 验证并标准化结果
            response = self._validate_and_normalize(result, search_results)
            
            logger.info(f"成功挖掘文献: {len(response.facts)} 个事实")
            
            return response
            
        except Exception as e:
            logger.error(f"挖掘文献时出错: {e}", exc_info=True)
            raise
    
    def _format_chunks(self, search_results: List[SearchResult]) -> str:
        """
        格式化文献片段
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            格式化后的字符串
        """
        chunks_text = []
        
        for i, result in enumerate(search_results, 1):
            paper_title = result.document_title or "未知论文"
            page_info = f" (页 {result.start_page})" if result.start_page else ""
            
            chunk_text = f"""--- 片段 {i} ---
Chunk ID: {result.chunk_id}
论文标题: {paper_title}{page_info}
相似度: {result.similarity:.3f}
内容: {result.content}"""
            
            chunks_text.append(chunk_text)
        
        return "\n\n".join(chunks_text)
    
    def _extract_facts(
        self,
        research_question: str,
        formatted_chunks: str
    ) -> dict:
        """
        调用 Qwen 提取科学事实
        
        Args:
            research_question: 研究问题
            formatted_chunks: 格式化的文献片段
            
        Returns:
            LLM 返回的字典
        """
        # 构建 Prompt
        prompt = LITERATURE_MINING_PROMPT_TEMPLATE.format(
            research_question=research_question,
            literature_chunks=formatted_chunks
        )
        
        # 定义 schema 示例
        schema_example = {
            "facts": [
                {
                    "fact_id": "fact_001",
                    "content": "事实内容",
                    "source_chunk_id": "chunk_id",
                    "source_paper_title": "论文标题",
                    "source_page": 1
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_001",
                    "fact_id": "fact_001",
                    "text": "证据原文",
                    "source_chunk_id": "chunk_id"
                }
            ],
            "source_papers": ["论文标题1"],
            "citation_map": [
                {
                    "paper_title": "论文标题",
                    "fact_ids": ["fact_001"],
                    "chunk_ids": ["chunk_id"]
                }
            ],
            "uncertain_points": ["不确定的点1"]
        }
        
        # 调用 Qwen
        return qwen_structured_chat(
            prompt=prompt,
            schema_example=schema_example
        )
    
    def _validate_and_normalize(
        self,
        result: dict,
        search_results: List[SearchResult]
    ) -> LiteratureMiningResponse:
        """
        验证并标准化结果
        
        Args:
            result: LLM 返回的字典
            search_results: 搜索结果
            
        Returns:
            LiteratureMiningResponse: 验证后的响应
        """
        # 确保必要字段存在
        for field in ["facts", "evidence", "source_papers", "citation_map", "uncertain_points"]:
            if field not in result:
                result[field] = []
        
        # 确保每个 fact 都有来源信息
        validated_facts = []
        for fact in result.get("facts", []):
            # 如果 LLM 返回的事实缺少来源信息，尝试从搜索结果中补充
            if "source_chunk_id" not in fact or not fact.get("source_chunk_id"):
                continue
            
            # 确保事实有完整结构
            validated_fact = {
                "fact_id": fact.get("fact_id", f"fact_{len(validated_facts) + 1:03d}"),
                "content": fact.get("content", ""),
                "source_chunk_id": fact.get("source_chunk_id", ""),
                "source_paper_title": fact.get("source_paper_title"),
                "source_page": fact.get("source_page")
            }
            
            validated_facts.append(validated_fact)
        
        result["facts"] = validated_facts
        
        # 使用 Pydantic 验证
        return LiteratureMiningResponse(**result)
    
    def _empty_response(self) -> LiteratureMiningResponse:
        """
        返回空响应
        
        Returns:
            LiteratureMiningResponse: 空响应
        """
        return LiteratureMiningResponse(
            facts=[],
            evidence=[],
            source_papers=[],
            citation_map=[],
            uncertain_points=["未找到相关文献片段"]
        )


# 全局单例
_agent_instance: Optional[LiteratureMiningAgent] = None


def get_literature_mining_agent() -> LiteratureMiningAgent:
    """获取 LiteratureMiningAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LiteratureMiningAgent()
    return _agent_instance
