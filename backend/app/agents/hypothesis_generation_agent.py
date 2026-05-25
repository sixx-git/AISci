"""
假设生成智能体 (HypothesisGenerationAgent)
"""
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)


HYPOTHESIS_GENERATION_PROMPT_TEMPLATE = """
你是一位资深的科研专家，擅长基于现有文献和知识缺口生成科学假设。

## 任务要求
基于提供的研究问题、事实、知识缺口和约束条件，生成 3-5 条科学假设。

## 重要原则
1. 使用归纳推理：从现有事实中总结规律，提出可验证的假设
2. 使用演绎推理：基于现有理论或知识缺口，推导出新的假设
3. 避免空泛套话：每条假设必须具体、明确，有针对性
4. 必须提供充分的理由依据
5. 明确说明创新点、可测试性、所需数据、可能的方法和风险

## 输入信息

研究问题：
{research_question}

已知事实：
{formatted_facts}

知识缺口：
{formatted_gaps}

约束条件：
{formatted_constraints}

## 输出格式要求
请严格按照以下 JSON 格式输出，不要添加额外解释或 markdown 标记：
{{
  "hypotheses": [
    {{
      "hypothesis": "清晰、具体、可检验的假设陈述",
      "rationale": "基于归纳/演绎推理的详细理由，引用相关事实或知识缺口",
      "novelty": "明确说明创新性，与现有研究的区别",
      "testability": "详细说明如何验证，包括实验设计或分析方法",
      "required_data": "具体列出所需的数据类型、来源和数量",
      "possible_method": "可能的研究方法和技术路线",
      "risk": "可能的风险、挑战和局限性"
    }}
  ],
  "summary": "对生成假设的简要总结和建议"
}}
"""


class HypothesisItem(BaseModel):
    """单个假设项"""
    hypothesis: str = Field(..., description="假设内容")
    rationale: str = Field(..., description="理论依据")
    novelty: str = Field(..., description="创新性")
    testability: str = Field(..., description="可测试性")
    required_data: str = Field(..., description="所需数据")
    possible_method: str = Field(..., description="可能的方法")
    risk: str = Field(..., description="风险")


class HypothesisGenerationResult(BaseModel):
    """假设生成结果"""
    hypotheses: List[HypothesisItem] = Field(..., description="生成的假设列表")
    summary: Optional[str] = Field(None, description="生成摘要")


class HypothesisGenerationAgent:
    """
    假设生成智能体
    基于研究问题、事实、知识缺口和约束条件生成科学假设
    """
    
    def __init__(self):
        pass
    
    def generate(
        self,
        research_question: str,
        facts: List[Dict[str, Any]],
        knowledge_gaps: List[Dict[str, Any]],
        constraints: List[str],
        project_id: Optional[str] = None
    ) -> HypothesisGenerationResult:
        """
        生成科学假设
        
        Args:
            research_question: 研究问题
            facts: 事实列表
            knowledge_gaps: 知识缺口列表
            constraints: 约束条件列表
            project_id: 项目ID（可选）
            
        Returns:
            生成的假设结果
        """
        try:
            logger.info(f"开始生成假设，研究问题：{research_question[:100]}...")
            
            # 格式化输入
            formatted_facts = self._format_facts(facts)
            formatted_gaps = self._format_gaps(knowledge_gaps)
            formatted_constraints = self._format_constraints(constraints)
            
            # 构建提示
            prompt = HYPOTHESIS_GENERATION_PROMPT_TEMPLATE.format(
                research_question=research_question,
                formatted_facts=formatted_facts,
                formatted_gaps=formatted_gaps,
                formatted_constraints=formatted_constraints
            )
            
            # 定义 schema 示例
            schema_example = {
                "hypotheses": [
                    {
                        "hypothesis": "示例假设",
                        "rationale": "示例理由",
                        "novelty": "示例创新点",
                        "testability": "示例可测试性",
                        "required_data": "示例所需数据",
                        "possible_method": "示例方法",
                        "risk": "示例风险"
                    }
                ],
                "summary": "示例摘要"
            }
            
            # 调用 LLM
            result_dict = qwen_structured_chat(prompt=prompt, schema_example=schema_example)
            
            # 验证并标准化结果
            result = self._validate_and_normalize_result(result_dict)
            
            logger.info(f"成功生成 {len(result.hypotheses)} 条假设")
            
            return result
            
        except Exception as e:
            logger.error(f"生成假设时出错：{e}", exc_info=True)
            raise
    
    def _format_facts(self, facts: List[Dict[str, Any]]) -> str:
        """格式化事实列表"""
        if not facts:
            return "（无事实）"
        
        formatted = []
        for idx, fact in enumerate(facts, 1):
            content = fact.get("content", str(fact))
            source = fact.get("source_paper_title", "")
            if source:
                formatted.append(f"{idx}. {content} (来源：{source})")
            else:
                formatted.append(f"{idx}. {content}")
        
        return "\n".join(formatted)
    
    def _format_gaps(self, gaps: List[Dict[str, Any]]) -> str:
        """格式化知识缺口列表"""
        if not gaps:
            return "（无知识缺口）"
        
        formatted = []
        for idx, gap in enumerate(gaps, 1):
            desc = gap.get("description", str(gap))
            value = gap.get("potential_value", "")
            if value:
                formatted.append(f"{idx}. {desc} (研究价值：{value})")
            else:
                formatted.append(f"{idx}. {desc}")
        
        return "\n".join(formatted)
    
    def _format_constraints(self, constraints: List[str]) -> str:
        """格式化约束条件列表"""
        if not constraints:
            return "（无约束条件）"
        
        return "\n".join([f"{idx}. {constraint}" for idx, constraint in enumerate(constraints, 1)])
    
    def _validate_and_normalize_result(self, result_dict: Dict[str, Any]) -> HypothesisGenerationResult:
        """验证并标准化结果"""
        # 确保必要字段存在
        if "hypotheses" not in result_dict or not isinstance(result_dict["hypotheses"], list):
            result_dict["hypotheses"] = []
        
        # 验证每个假设
        validated_hypotheses = []
        for hypo in result_dict["hypotheses"]:
            if not isinstance(hypo, dict):
                continue
            
            # 确保所有必要字段存在
            for field in ["hypothesis", "rationale", "novelty", "testability", "required_data", "possible_method", "risk"]:
                if field not in hypo:
                    hypo[field] = ""
            
            validated_hypotheses.append(HypothesisItem(**hypo))
        
        # 确保假设数量在 3-5 之间
        if len(validated_hypotheses) < 3:
            logger.warning(f"生成的假设数量不足 3 条，实际：{len(validated_hypotheses)}")
        if len(validated_hypotheses) > 5:
            logger.warning(f"生成的假设数量超过 5 条，截断为 5 条")
            validated_hypotheses = validated_hypotheses[:5]
        
        result_dict["hypotheses"] = validated_hypotheses
        
        return HypothesisGenerationResult(**result_dict)


# 全局单例
_agent_instance: Optional[HypothesisGenerationAgent] = None


def get_hypothesis_generation_agent() -> HypothesisGenerationAgent:
    """获取 HypothesisGenerationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = HypothesisGenerationAgent()
    return _agent_instance
