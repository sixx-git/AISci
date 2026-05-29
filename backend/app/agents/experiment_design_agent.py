"""
实验设计智能体 (ExperimentDesignAgent)
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.skills.experiment.experiment_sanity_check_skill import ExperimentSanityCheckSkill
from app.skills.data.multimodal_ingest_skill import MultimodalDataIngestSkill
from app.skills.data.multimodal_linking_skill import MultimodalDataLinkingSkill
from app.skills.data.dataset_discovery_skill import DatasetDiscoverySkill

logger = logging.getLogger(__name__)


class ExperimentDesignResult(BaseModel):
    """实验设计结果（标准化输出）"""
    methods: str = Field("", description="研究方法")
    datasets: str = Field("", description="所需数据集")
    source_data: str = Field("", description="源数据说明")
    target_data: str = Field("", description="目标数据说明")
    baselines: str = Field("", description="基线方法")
    metrics: str = Field("", description="评估指标")
    experimental_steps: str = Field("", description="实验步骤")
    expected_results: str = Field("", description="预期结果")
    limitations: str = Field("", description="局限性")
    skill_outputs: Dict[str, Any] = Field(default_factory=dict, description="Skill 执行输出")

    @field_validator(
        "datasets", "baselines", "metrics",
        "experimental_steps", "limitations",
        mode="before"
    )
    @classmethod
    def _list_to_str(cls, v):
        """LLM 可能返回列表，自动转为换行分隔的字符串"""
        if isinstance(v, list):
            return "\n".join(
                item if isinstance(item, str) else item.get("name", str(item))
                for item in v
            )
        return v


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
        risk: Optional[str] = None,
        data_files: Optional[List[str]] = None,
        literature_facts: Optional[List[Dict[str, Any]]] = None,
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
            data_files: 项目数据文件路径列表
            literature_facts: 文献挖掘事实列表
            
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
                schema_example=schema_example,
                prompt_version="experiment_design"
            )
            
            # 验证并标准化结果
            result = self._validate_and_normalize_result(result_dict)

            # ── 运行实验真实性审查 + 多模态数据 Skill ──
            result["skill_outputs"] = self._run_skills_sync(
                result, hypothesis, data_files or [], literature_facts or []
            )

            logger.info("实验设计完成")

            return ExperimentDesignResult(**result)
            
        except Exception as e:
            logger.error(f"设计实验时出错：{e}", exc_info=True)
            raise
    
    @staticmethod
    def _run_skills_sync(
        result: Dict[str, Any],
        hypothesis: str,
        data_files: List[str],
        literature_facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            outputs = {}
            try:
                skill = ExperimentSanityCheckSkill()
                skill_result = await skill.run(
                    input_data={"experiment_design": result},
                    context={"stage": "experiment_design"},
                )
                outputs["experiment_sanity_check"] = {
                    "success": skill_result.success,
                    "data": skill_result.data,
                    "warnings": skill_result.warnings,
                    "errors": skill_result.errors,
                }
            except Exception as e:
                logger.warning(f"ExperimentSanityCheckSkill 失败: {e}")
                outputs["experiment_sanity_check"] = {"success": False, "error": str(e)}

            multimodal_datasets = []
            if data_files:
                try:
                    ingest_skill = MultimodalDataIngestSkill()
                    ingest_result = await ingest_skill.run(
                        input_data={
                            "file_paths": data_files,
                            "project_id": result.get("project_id", ""),
                            "missing_strategy": "median",
                        },
                        context={"stage": "experiment_design"},
                    )
                    multimodal_datasets = ingest_result.data.get("datasets", [])
                    outputs["multimodal_data_ingest"] = {
                        "success": ingest_result.success,
                        "data": ingest_result.data,
                        "warnings": ingest_result.warnings,
                        "errors": ingest_result.errors,
                    }
                except Exception as e:
                    logger.warning(f"MultimodalDataIngestSkill 失败: {e}")
                    outputs["multimodal_data_ingest"] = {"success": False, "error": str(e)}

            if literature_facts or multimodal_datasets:
                try:
                    linking_skill = MultimodalDataLinkingSkill()
                    linking_result = await linking_skill.run(
                        input_data={
                            "literature_facts": literature_facts,
                            "multimodal_datasets": multimodal_datasets,
                            "hypothesis": hypothesis,
                        },
                        context={"stage": "experiment_design"},
                    )
                    outputs["multimodal_data_linking"] = {
                        "success": linking_result.success,
                        "data": linking_result.data,
                        "warnings": linking_result.warnings,
                        "errors": linking_result.errors,
                    }
                except Exception as e:
                    logger.warning(f"MultimodalDataLinkingSkill 失败: {e}")
                    outputs["multimodal_data_linking"] = {"success": False, "error": str(e)}

            try:
                discovery_skill = DatasetDiscoverySkill()
                discovery_result = await discovery_skill.run(
                    input_data={
                        "research_question": hypothesis,
                        "keywords": [],
                        "max_results": 10,
                    },
                    context={"stage": "experiment_design"},
                )
                outputs["dataset_discovery"] = {
                    "success": discovery_result.success,
                    "data": discovery_result.data,
                    "warnings": discovery_result.warnings,
                    "errors": discovery_result.errors,
                }
            except Exception as e:
                logger.warning(f"DatasetDiscoverySkill 失败: {e}")
                outputs["dataset_discovery"] = {"success": False, "error": str(e)}

            return outputs

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"Skills 异常: {e}")
            return {}

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
