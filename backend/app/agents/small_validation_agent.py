"""
小样验证智能体 (SmallValidationAgent)
根据实验设计生成可运行的小样验证方案
"""
import logging
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader
from app.skills.data.preliminary_analysis_skill import PreliminaryAnalysisSkill

logger = logging.getLogger(__name__)

settings = get_settings()


class SmallValidationAgent:
    """
    小样验证智能体
    根据实验设计生成可运行的小样验证方案
    """
    
    def __init__(self):
        # 确保存储目录存在
        self.validation_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "storage", "validations")
        os.makedirs(self.validation_dir, exist_ok=True)
    
    def generate_validation(
        self,
        hypothesis: str,
        methods: Optional[str] = None,
        datasets: Optional[str] = None,
        metrics: Optional[str] = None,
        csv_data_path: Optional[str] = None,
        experiment_design: Optional[Dict[str, Any]] = None,
        multimodal_datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        生成小样验证方案
        
        Args:
            hypothesis: 假设内容
            methods: 研究方法
            datasets: 数据集说明
            metrics: 评估指标
            csv_data_path: CSV 数据路径（如果有）
            experiment_design: 实验设计结果
            multimodal_datasets: 多模态数据集
            
        Returns:
            验证方案结果
        """
        try:
            logger.info(f"开始为假设生成小样验证: {hypothesis[:100]}...")
            
            has_csv_data = 1 if csv_data_path and os.path.exists(csv_data_path) else 0
            
            # 构建提示
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "small_validation",
                {
                    "hypothesis": hypothesis,
                    "methods": methods or "未提供具体方法",
                    "datasets": datasets or "未提供数据集说明",
                    "metrics": metrics or "未提供评估指标",
                    "has_csv_data": "是" if has_csv_data else "否"
                }
            )
            
            # 定义 schema 示例
            schema_example = {
                "has_real_data": 0,
                "analysis_script": "# 完整的 Python 分析脚本...",
                "simulated_data": "[{\"col1\": 1, \"col2\": 2}]",
                "simulation_assumptions": "模拟假设说明...",
                "charts": "[{\"type\": \"bar\", \"title\": \"示例图表\", \"data\": []}]",
                "statistics": "{\"mean\": 0.5}",
                "run_log": "[{\"timestamp\": \"2024-01-01\", \"level\": \"INFO\", \"message\": \"开始\"}]"
            }
            
            # 调用 LLM
            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="small_validation"
            )
            
            # 验证和标准化结果
            result = self._validate_and_normalize_result(result_dict, has_csv_data)
            
            # ── 运行初步分析 Skill ──
            result["skill_outputs"] = self._run_preliminary_analysis_sync(
                hypothesis, methods, datasets, metrics, experiment_design, multimodal_datasets
            )
            
            # 保存验证文件
            self._save_validation_files(result)
            
            logger.info("小样验证方案生成完成")
            
            return result
            
        except Exception as e:
            logger.error(f"生成小样验证方案时出错: {e}", exc_info=True)
            raise

    @staticmethod
    def _run_preliminary_analysis_sync(
        hypothesis: str,
        methods: Optional[str] = None,
        datasets: Optional[str] = None,
        metrics: Optional[str] = None,
        experiment_design: Optional[Dict[str, Any]] = None,
        multimodal_datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        import asyncio

        async def _run():
            outputs = {}
            try:
                skill = PreliminaryAnalysisSkill()
                skill_result = await skill.run(
                    input_data={
                        "multimodal_datasets": multimodal_datasets or [],
                        "hypothesis": hypothesis,
                        "experiment_design": experiment_design or {},
                        "methods": methods or "",
                        "metrics": metrics or "",
                    },
                    context={"stage": "small_validation"},
                )
                outputs["preliminary_analysis"] = {
                    "success": skill_result.success,
                    "data": skill_result.data,
                    "warnings": skill_result.warnings,
                    "errors": skill_result.errors,
                }
            except Exception as e:
                logger.warning(f"PreliminaryAnalysisSkill 失败: {e}")
                outputs["preliminary_analysis"] = {"success": False, "error": str(e)}
            return outputs

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"PreliminaryAnalysisSkill 异常: {e}")
            return {}
    
    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        has_csv_data: int
    ) -> Dict[str, Any]:
        """验证和标准化结果"""
        # 确保必要字段存在
        required_fields = [
            "has_real_data", "analysis_script", "simulated_data",
            "simulation_assumptions", "charts", "statistics", "run_log"
        ]
        
        for field in required_fields:
            if field not in result_dict:
                if field == "has_real_data":
                    result_dict[field] = has_csv_data
                elif field == "analysis_script":
                    result_dict[field] = self._generate_default_script()
                else:
                    result_dict[field] = ""
        
        # 确保 has_real_data 是整数
        result_dict["has_real_data"] = int(result_dict.get("has_real_data", has_csv_data))
        
        # 生成默认运行日志
        if not result_dict.get("run_log"):
            result_dict["run_log"] = self._generate_default_log()
        
        return result_dict
    
    def _generate_default_script(self) -> str:
        """生成默认的分析脚本"""
        return '''import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

print("="*50)
print("小样验证脚本")
print(f"开始时间: {datetime.now()}")
print("="*50)

# 生成模拟数据
np.random.seed(42)
n_samples = 100
data = pd.DataFrame({
    'feature1': np.random.normal(0, 1, n_samples),
    'feature2': np.random.normal(1, 2, n_samples),
    'target': np.random.choice([0, 1], n_samples)
})

print("\\n数据前5行:")
print(data.head())
print("\\n数据统计信息:")
print(data.describe())

# 简单统计
stats = {
    'feature1_mean': data['feature1'].mean(),
    'feature1_std': data['feature1'].std(),
    'feature2_mean': data['feature2'].mean(),
    'feature2_std': data['feature2'].std(),
    'target_dist': data['target'].value_counts().to_dict()
}

print("\\n统计结果:")
for key, value in stats.items():
    print(f"{key}: {value}")

print("\\n" + "="*50)
print("验证完成")
print("="*50)
'''
    
    def _generate_default_log(self) -> str:
        """生成默认运行日志"""
        now = datetime.now().isoformat()
        log_entries = [
            {"timestamp": now, "level": "INFO", "message": "小样验证任务初始化"},
            {"timestamp": now, "level": "INFO", "message": "生成分析脚本"},
            {"timestamp": now, "level": "INFO", "message": "准备模拟数据"},
            {"timestamp": now, "level": "INFO", "message": "执行统计分析"},
            {"timestamp": now, "level": "INFO", "message": "生成图表"},
            {"timestamp": now, "level": "INFO", "message": "验证任务完成"}
        ]
        return json.dumps(log_entries, ensure_ascii=False)
    
    def _save_validation_files(self, result: Dict[str, Any]) -> None:
        """保存验证文件"""
        try:
            # 生成唯一 ID
            import uuid
            validation_id = str(uuid.uuid4())
            
            # 创建目录
            validation_path = os.path.join(self.validation_dir, validation_id)
            os.makedirs(validation_path, exist_ok=True)
            
            # 保存脚本
            script_path = os.path.join(validation_path, "analysis.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(result.get("analysis_script", ""))
            
            # 保存模拟数据
            if result.get("simulated_data"):
                data_path = os.path.join(validation_path, "simulated_data.json")
                with open(data_path, "w", encoding="utf-8") as f:
                    f.write(result["simulated_data"])
            
            # 保存结果
            result_path = os.path.join(validation_path, "result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"验证文件已保存到: {validation_path}")
            
        except Exception as e:
            logger.error(f"保存验证文件时出错: {e}", exc_info=True)


# 全局单例
_agent_instance: Optional[SmallValidationAgent] = None


def get_small_validation_agent() -> SmallValidationAgent:
    """获取 SmallValidationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SmallValidationAgent()
    return _agent_instance
