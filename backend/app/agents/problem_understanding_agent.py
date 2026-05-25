"""
问题理解智能体 (ProblemUnderstandingAgent)
"""
import json
import logging
from typing import Optional, List
from pydantic import BaseModel, Field

from app.services.qwen_client import (
    get_qwen_client,
    qwen_structured_chat
)

logger = logging.getLogger(__name__)


class ProblemUnderstandingRequest(BaseModel):
    """问题理解请求"""
    research_question: str = Field(..., description="用户的研究问题", example="如何利用机器学习提高医学影像诊断的准确率？")
    domain_description: Optional[str] = Field(None, description="领域描述", example="医学影像、人工智能、深度学习")


class ProblemUnderstandingResponse(BaseModel):
    """问题理解响应"""
    problem_statement: str = Field(..., description="明确的研究问题陈述")
    research_domain: str = Field(..., description="研究领域")
    keywords: List[str] = Field(..., description="关键词列表")
    scope_boundary: str = Field(..., description="研究范围和边界定义")
    constraints: List[str] = Field(..., description="约束条件")
    expected_output: List[str] = Field(..., description="期望的研究输出")


# Prompt 模板
PROBLEM_UNDERSTANDING_PROMPT_TEMPLATE = """你是一位专业的研究顾问，擅长理解和梳理研究问题。

## 任务要求
请分析用户的研究问题，输出结构化的 JSON 格式，包含以下字段：
- problem_statement: 明确的研究问题陈述，避免泛化
- research_domain: 研究领域
- keywords: 关键词列表
- scope_boundary: 研究范围和边界定义
- constraints: 约束条件
- expected_output: 期望的研究输出

## 重要原则
1. 明确研究问题：将模糊的问题转化为具体、可研究的问题陈述
2. 边界定义：清晰说明研究的范围、不研究的内容、适用场景
3. 避免泛化：避免过于宽泛的描述，要具体、可操作
4. 紧扣主题：所有分析都要围绕用户的研究问题展开

## 用户输入
研究问题：{research_question}
领域描述：{domain_description}

## 输出格式要求
请严格按照以下 JSON 格式输出，不要添加额外解释或 markdown 标记：
{{
  "problem_statement": "string",
  "research_domain": "string",
  "keywords": ["keyword1", "keyword2"],
  "scope_boundary": "string",
  "constraints": ["constraint1", "constraint2"],
  "expected_output": ["output1", "output2"]
}}"""


class ProblemUnderstandingAgent:
    """问题理解智能体"""
    
    def __init__(self):
        self.qwen_client = get_qwen_client()
    
    def analyze(
        self,
        research_question: str,
        domain_description: Optional[str] = None
    ) -> ProblemUnderstandingResponse:
        """
        分析研究问题
        
        Args:
            research_question: 用户的研究问题
            domain_description: 领域描述
            
        Returns:
            ProblemUnderstandingResponse: 结构化分析结果
        """
        try:
            # 构建 Prompt
            prompt = self._build_prompt(research_question, domain_description)
            
            # 定义输出 schema 示例
            schema_example = {
                "problem_statement": "示例研究问题陈述",
                "research_domain": "示例研究领域",
                "keywords": ["关键词1", "关键词2"],
                "scope_boundary": "示例研究范围定义",
                "constraints": ["约束1", "约束2"],
                "expected_output": ["输出1", "输出2"]
            }
            
            # 调用 Qwen 结构化对话
            result = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example
            )
            
            # 验证并返回结果
            response = self._validate_and_normalize(result)
            
            logger.info(f"成功分析研究问题: {research_question[:50]}...")
            
            return response
            
        except Exception as e:
            logger.error(f"分析研究问题时出错: {e}", exc_info=True)
            raise
    
    def _build_prompt(
        self,
        research_question: str,
        domain_description: Optional[str] = None
    ) -> str:
        """
        构建 Prompt
        
        Args:
            research_question: 研究问题
            domain_description: 领域描述
            
        Returns:
            完整的 Prompt 字符串
        """
        domain_str = domain_description if domain_description else "未指定"
        
        return PROBLEM_UNDERSTANDING_PROMPT_TEMPLATE.format(
            research_question=research_question,
            domain_description=domain_str
        )
    
    def _validate_and_normalize(
        self,
        result: dict
    ) -> ProblemUnderstandingResponse:
        """
        验证并标准化结果
        
        Args:
            result: LLM 返回的字典
            
        Returns:
            ProblemUnderstandingResponse: 验证后的响应
        """
        # 确保必要字段存在
        required_fields = [
            "problem_statement",
            "research_domain",
            "keywords",
            "scope_boundary",
            "constraints",
            "expected_output"
        ]
        
        for field in required_fields:
            if field not in result:
                result[field] = "" if field != "keywords" and field != "constraints" and field != "expected_output" else []
        
        # 确保列表字段是列表类型
        for list_field in ["keywords", "constraints", "expected_output"]:
            if not isinstance(result[list_field], list):
                result[list_field] = []
        
        # 使用 Pydantic 验证
        return ProblemUnderstandingResponse(**result)


# 全局单例
_agent_instance: Optional[ProblemUnderstandingAgent] = None


def get_problem_understanding_agent() -> ProblemUnderstandingAgent:
    """获取 ProblemUnderstandingAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ProblemUnderstandingAgent()
    return _agent_instance
