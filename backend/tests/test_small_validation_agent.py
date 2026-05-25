"""
SmallValidationAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open

from app.agents.small_validation_agent import (
    SmallValidationAgent,
    SMALL_VALIDATION_PROMPT_TEMPLATE
)


class TestSmallValidationAgent(TestCase):
    """SmallValidationAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = SmallValidationAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("分析脚本", SMALL_VALIDATION_PROMPT_TEMPLATE)
        self.assertIn("模拟数据", SMALL_VALIDATION_PROMPT_TEMPLATE)
        self.assertIn("简单图表", SMALL_VALIDATION_PROMPT_TEMPLATE)
        self.assertIn("统计结果", SMALL_VALIDATION_PROMPT_TEMPLATE)
        self.assertIn("运行日志", SMALL_VALIDATION_PROMPT_TEMPLATE)
        self.assertIn("pandas", SMALL_VALIDATION_PROMPT_TEMPLATE)
    
    def test_validate_and_normalize_result(self):
        """测试验证和标准化结果"""
        # 测试完整结果
        complete_result = {
            "has_real_data": 0,
            "analysis_script": "import pandas as pd\n...",
            "simulated_data": "[{\"col\": 1}]",
            "simulation_assumptions": "模拟假设...",
            "charts": "[{\"type\": \"bar\"}]",
            "statistics": "{\"mean\": 0.5}",
            "run_log": "[{\"message\": \"开始\"}]"
        }
        
        result = self.agent._validate_and_normalize_result(complete_result, 0)
        
        # 验证所有字段都存在
        self.assertIn("has_real_data", result)
        self.assertIn("analysis_script", result)
        self.assertIn("simulated_data", result)
        self.assertIn("simulation_assumptions", result)
        self.assertIn("charts", result)
        self.assertIn("statistics", result)
        self.assertIn("run_log", result)
        
        # 测试缺失字段的情况
        incomplete_result = {
            "has_real_data": 1
        }
        
        result = self.agent._validate_and_normalize_result(incomplete_result, 1)
        
        # 验证缺失字段被补全
        self.assertEqual(result["has_real_data"], 1)
        self.assertTrue(len(result["analysis_script"]) > 0)
        self.assertTrue(len(result["run_log"]) > 0)
    
    def test_generate_default_script(self):
        """测试生成默认脚本"""
        script = self.agent._generate_default_script()
        
        # 验证脚本包含必要的导入
        self.assertIn("import pandas", script)
        self.assertIn("import numpy", script)
        self.assertIn("import matplotlib", script)
        self.assertIn("import seaborn", script)
        
        # 验证脚本包含关键逻辑
        self.assertIn("np.random.seed", script)
        self.assertIn("pd.DataFrame", script)
        self.assertIn("data.describe()", script)
    
    def test_generate_default_log(self):
        """测试生成默认日志"""
        log = self.agent._generate_default_log()
        
        # 验证日志格式正确
        self.assertIn("timestamp", log)
        self.assertIn("level", log)
        self.assertIn("message", log)
        self.assertIn("INFO", log)
    
    @patch("app.agents.small_validation_agent.qwen_structured_chat")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_validation_success(
        self,
        mock_file,
        mock_makedirs,
        mock_qwen
    ):
        """测试生成验证方案成功"""
        test_hypothesis = "混合模型在分类任务中表现优于单一模型"
        
        # 模拟 LLM 返回
        mock_qwen_result = {
            "has_real_data": 0,
            "analysis_script": """import pandas as pd
import numpy as np

# 生成模拟数据
np.random.seed(42)
data = pd.DataFrame({
    'model_a': np.random.normal(0.85, 0.05, 100),
    'model_b': np.random.normal(0.82, 0.06, 100),
    'hybrid': np.random.normal(0.89, 0.04, 100)
})

print(data.describe())""",
            "simulated_data": """[
  {"model_a": 0.85, "model_b": 0.82, "hybrid": 0.89},
  {"model_a": 0.88, "model_b": 0.80, "hybrid": 0.91}
]""",
            "simulation_assumptions": "假设：1. 三个模型在相同数据集上评估；2. 指标为准确率；3. 混合模型整合了两个单一模型的优势",
            "charts": """[
  {"type": "bar", "title": "模型性能对比", "data": [{"model": "Model A", "score": 0.85}, {"model": "Model B", "score": 0.82}, {"model": "Hybrid", "score": 0.89}]},
  {"type": "box", "title": "性能分布", "data": []}
]""",
            "statistics": """{"model_a_mean": 0.85, "model_b_mean": 0.82, "hybrid_mean": 0.89, "improvement": 0.07}""",
            "run_log": """[
  {"timestamp": "2024-01-01 10:00:00", "level": "INFO", "message": "开始验证假设"},
  {"timestamp": "2024-01-01 10:00:01", "level": "INFO", "message": "生成模拟数据"},
  {"timestamp": "2024-01-01 10:00:02", "level": "INFO", "message": "执行统计分析"},
  {"timestamp": "2024-01-01 10:00:03", "level": "INFO", "message": "生成图表"},
  {"timestamp": "2024-01-01 10:00:04", "level": "INFO", "message": "验证完成：混合模型表现最佳"}
]"""
        }
        
        mock_qwen.return_value = mock_qwen_result
        
        # 调用生成验证
        result = self.agent.generate_validation(
            hypothesis=test_hypothesis,
            methods="使用对比实验评估三个模型",
            datasets="使用公开分类数据集",
            metrics="准确率、F1-score"
        )
        
        # 验证
        self.assertIsNotNone(result)
        self.assertIn("has_real_data", result)
        self.assertIn("analysis_script", result)
        self.assertIn("simulated_data", result)
        self.assertIn("simulation_assumptions", result)
        self.assertIn("charts", result)
        self.assertIn("statistics", result)
        self.assertIn("run_log", result)
        
        self.assertTrue(len(result["analysis_script"]) > 0)
        self.assertTrue(len(result["simulation_assumptions"]) > 0)
        
        mock_qwen.assert_called_once()
        mock_makedirs.assert_called()


if __name__ == '__main__':
    unittest.main()
