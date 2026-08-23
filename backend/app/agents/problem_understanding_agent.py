"""
问题理解智能体 (ProblemUnderstandingAgent)
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import (
    qwen_structured_chat
)
from app.services.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class ResearchObject(BaseModel):
    """研究对象拆解（开题报告：内/外/边界）"""
    internal: str = Field(default="", description="内部结构/组成/机制")
    external: str = Field(default="", description="外部环境/条件")
    boundary: str = Field(default="", description="研究边界")


class ProblemUnderstandingRequest(BaseModel):
    """问题理解请求"""
    research_question: str = Field(..., description="用户的研究问题", example="如何利用机器学习提高医学影像诊断的准确率？")
    domain_description: Optional[str] = Field(None, description="领域描述", example="医学影像、人工智能、深度学习")


class ProblemUnderstandingResponse(BaseModel):
    """问题理解响应"""
    problem_statement: str = Field(..., description="清晰明确的研究问题陈述")
    research_domain: str = Field(..., description="研究领域")
    keywords: List[str] = Field(..., description="关键词列表")
    scope_boundary: str = Field(..., description="研究范围和边界定义")
    constraints: List[str] = Field(..., description="约束条件")
    expected_output: List[str] = Field(..., description="期望的研究输出")
    main_contradiction: str = Field(default="", description="主要矛盾（一句话）")
    phenomenon_contradiction: str = Field(default="", description="现象/理论矛盾来源")
    research_object: ResearchObject = Field(
        default_factory=ResearchObject,
        description="研究对象拆解",
    )
    decomposition_notes: str = Field(default="", description="对象演化或机制说明")
    research_significance: str = Field(default="", description="真实科研价值")


def build_scientific_logic_constraints(pu: Dict[str, Any]) -> List[str]:
    """从问题理解结果构建下游 Agent 可用的科学逻辑约束。"""
    if not isinstance(pu, dict):
        return []

    lines: List[str] = []
    main = str(pu.get("main_contradiction") or "").strip()
    if main:
        lines.append(f"[科学逻辑] 主要矛盾: {main}")

    phenomenon = str(pu.get("phenomenon_contradiction") or "").strip()
    if phenomenon:
        lines.append(f"[科学逻辑] 矛盾来源: {phenomenon}")

    ro = pu.get("research_object") or {}
    if isinstance(ro, dict):
        internal = str(ro.get("internal") or "").strip()
        external = str(ro.get("external") or "").strip()
        boundary = str(ro.get("boundary") or "").strip()
        if internal or external or boundary:
            lines.append(
                "[科学逻辑] 研究对象拆解: "
                f"内部={internal or '—'}; 外部={external or '—'}; 边界={boundary or '—'}"
            )

    notes = str(pu.get("decomposition_notes") or "").strip()
    if notes:
        lines.append(f"[科学逻辑] 机制/演化: {notes}")

    significance = str(pu.get("research_significance") or "").strip()
    if significance:
        lines.append(f"[科学逻辑] 科研价值: {significance}")

    expected = pu.get("expected_output") or []
    if isinstance(expected, list):
        items = [str(x).strip() for x in expected if str(x).strip()]
        if items:
            lines.append(f"[科学逻辑] 研究目的: {'; '.join(items[:5])}")

    return lines


def resolve_research_question_from_pu(
    pu: Dict[str, Any],
    fallback: str = "",
) -> str:
    """从问题理解结果解析研究问题文本。"""
    if not isinstance(pu, dict):
        return fallback
    for key in ("research_question", "problem_statement"):
        value = str(pu.get(key) or "").strip()
        if value:
            return value
    return fallback


class ProblemUnderstandingAgent:
    """问题理解智能体"""
    
    def __init__(self):
        pass
    
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
                "expected_output": ["输出1", "输出2"],
                "main_contradiction": "示例主要矛盾",
                "phenomenon_contradiction": "示例矛盾来源",
                "research_object": {
                    "internal": "内部因素",
                    "external": "外部因素",
                    "boundary": "研究边界",
                },
                "decomposition_notes": "示例机制说明",
                "research_significance": "示例科研价值",
            }
            
            # 调用 Qwen 结构化对话
            result = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="problem_understanding"
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
        prompt_loader = get_prompt_loader()
        
        return prompt_loader.render_template(
            "problem_understanding",
            {
                "research_question": research_question,
                "domain_description": domain_str
            }
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
            "expected_output",
        ]
        
        for field in required_fields:
            if field not in result:
                result[field] = "" if field != "keywords" and field != "constraints" and field != "expected_output" else []
        
        # 科学逻辑扩展字段默认值
        for field in (
            "main_contradiction",
            "phenomenon_contradiction",
            "decomposition_notes",
            "research_significance",
        ):
            result.setdefault(field, "")

        ro = result.get("research_object")
        if not isinstance(ro, dict):
            result["research_object"] = {"internal": "", "external": "", "boundary": ""}
        else:
            result["research_object"] = {
                "internal": str(ro.get("internal") or ""),
                "external": str(ro.get("external") or ""),
                "boundary": str(ro.get("boundary") or ""),
            }
        
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
