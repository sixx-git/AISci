"""
实验设计智能体 (ExperimentDesignAgent)
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)


EXPERIMENT_DESIGN_PROMPT_TEMPLATE = """你是一位专业的科研实验设计专家。请根据提供的科学假设，设计一个完整的实验方案。

## 输入假设
{hypothesis_info}

## 输出要求
请按照"科学假设与研究计划"的规范，输出以下字段：

1. **methods**（研究方法）：详细描述你将使用的研究方法、算法或技术。包括方法的原理、选择理由、具体实现方式等。
2. **datasets**（数据集）：列出所有将使用的数据集。包括数据集名称、来源、规模、特点、获取方式等。
3. **source_data**（源数据）：描述实验中使用的原始数据或输入数据的格式、内容、预处理方式等。
4. **target_data**（目标数据）：描述实验的预期输出或结果数据的格式、内容等。
5. **baselines**（基线方法）：列出将用于对比的基线方法。包括基线方法的名称、实现方式、为什么选择这些基线。
6. **metrics**（评估指标）：详细描述将用于评估实验结果的评估指标。包括指标的定义、计算方式、为什么选择这些指标。
7. **experimental_steps**（实验步骤）：分步骤详细描述实验的执行流程。包括数据准备、模型训练、评估、对比分析等。
8. **expected_results**（预期结果）：描述你预期通过这个实验获得的结果。包括可能的发现、验证假设的方式等。
9. **limitations**（局限性）：分析这个实验设计可能存在的局限性。包括数据限制、方法限制、时间限制等。

## 输出格式要求
请严格按照以下 JSON 格式输出，不要添加额外解释或 markdown 标记：
{{
  "methods": "详细描述研究方法",
  "datasets": "详细描述数据集",
  "source_data": "详细描述源数据",
  "target_data": "详细描述目标数据",
  "baselines": "详细描述基线方法",
  "metrics": "详细描述评估指标",
  "experimental_steps": "分步骤详细描述实验流程",
  "expected_results": "详细描述预期结果",
  "limitations": "详细分析局限性"
}}

## 注意事项
- 所有描述必须具体、详细、可操作
- 符合科研论文的写作规范
- 考虑实验的可行性和可重复性
- 突出验证假设的关键环节
"""


class ExperimentDesignAgent:
    """
    实验设计智能体
    根据最高分假设自动生成完整的实验设计
    """
    
    def __init__(self):
        pass
    
    def design_experiment(
        self,
        hypothesis: str,
        rationale: Optional[str] = None,
        novelty: Optional[str] = None,
        testability: Optional[str] = None,
        required_data: Optional[str] = None,
        possible_method: Optional[str] = None,
        risk: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        设计实验
        
        Args:
            hypothesis: 假设内容
            rationale: 理论依据
            novelty: 创新性
            testability: 可测试性
            required_data: 所需数据
            possible_method: 可能的方法
            risk: 风险
            
        Returns:
            实验设计结果
        """
        try:
            logger.info(f"开始为假设设计实验：{hypothesis[:100]}...")
            
            # 格式化假设信息
            hypothesis_info = self._format_hypothesis_info(
                hypothesis, rationale, novelty, 
                testability, required_data, possible_method, risk
            )
            
            # 构建提示
            prompt = EXPERIMENT_DESIGN_PROMPT_TEMPLATE.format(
                hypothesis_info=hypothesis_info
            )
            
            # 定义 schema 示例
            schema_example = {
                "methods": "详细描述研究方法...",
                "datasets": "详细描述数据集...",
                "source_data": "详细描述源数据...",
                "target_data": "详细描述目标数据...",
                "baselines": "详细描述基线方法...",
                "metrics": "详细描述评估指标...",
                "experimental_steps": "分步骤详细描述实验流程...",
                "expected_results": "详细描述预期结果...",
                "limitations": "详细分析局限性..."
            }
            
            # 调用 LLM
            result_dict = qwen_structured_chat(
                prompt=prompt, 
                schema_example=schema_example
            )
            
            # 验证并标准化结果
            result = self._validate_and_normalize_result(result_dict)
            
            logger.info("实验设计完成")
            
            return result
            
        except Exception as e:
            logger.error(f"设计实验时出错：{e}", exc_info=True)
            raise
    
    def _format_hypothesis_info(
        self,
        hypothesis: str,
        rationale: Optional[str] = None,
        novelty: Optional[str] = None,
        testability: Optional[str] = None,
        required_data: Optional[str] = None,
        possible_method: Optional[str] = None,
        risk: Optional[str] = None
    ) -> str:
        """格式化假设信息"""
        info = f"**假设内容**：{hypothesis}\n\n"
        
        if rationale:
            info += f"**理论依据**：{rationale}\n\n"
        if novelty:
            info += f"**创新性**：{novelty}\n\n"
        if testability:
            info += f"**可测试性**：{testability}\n\n"
        if required_data:
            info += f"**所需数据**：{required_data}\n\n"
        if possible_method:
            info += f"**可能的方法**：{possible_method}\n\n"
        if risk:
            info += f"**风险**：{risk}\n\n"
        
        return info
    
    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证并标准化结果"""
        required_fields = [
            "methods", "datasets", "source_data", "target_data",
            "baselines", "metrics", "experimental_steps",
            "expected_results", "limitations"
        ]
        
        # 确保所有必填字段存在
        for field in required_fields:
            if field not in result_dict or not result_dict[field]:
                result_dict[field] = f"待补充{field}"
        
        return result_dict


# 全局单例
_agent_instance: Optional[ExperimentDesignAgent] = None


def get_experiment_design_agent() -> ExperimentDesignAgent:
    """获取 ExperimentDesignAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ExperimentDesignAgent()
    return _agent_instance
