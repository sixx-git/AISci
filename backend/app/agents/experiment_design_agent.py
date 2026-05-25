"""
实验设计智能体 (ExperimentDesignAgent)
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


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
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "experiment_design",
                {"hypothesis_info": hypothesis_info}
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
