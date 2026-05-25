"""
ReportGenerationAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open

from app.agents.report_generation_agent import (
    ReportGenerationAgent,
    REPORT_GENERATION_PROMPT_TEMPLATE
)


class TestReportGenerationAgent(TestCase):
    """ReportGenerationAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = ReportGenerationAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("Problem Statement", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Rationale", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Technical Details", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Datasets", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Source", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Target", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Paper Title", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Paper Abstract", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Methods", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Experiments", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("Results", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("References", REPORT_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("禁止虚构", REPORT_GENERATION_PROMPT_TEMPLATE)
    
    def test_format_input(self):
        """测试格式化输入"""
        project_info = {"title": "测试项目"}
        problem_understanding = {"problem": "测试问题"}
        literature_facts = [{"content": "事实1"}]
        citation_map = [{"source": "文献1"}]
        knowledge_gaps = {"gaps": ["缺口1"]}
        final_hypothesis = {"hypothesis": "假设1"}
        experiment_design = {"methods": "方法1"}
        small_validation = {"result": "结果1"}
        
        formatted = self.agent._format_input(
            project_info,
            problem_understanding,
            literature_facts,
            citation_map,
            knowledge_gaps,
            final_hypothesis,
            experiment_design,
            small_validation
        )
        
        # 验证所有键都存在
        self.assertIn("project_info", formatted)
        self.assertIn("problem_understanding", formatted)
        self.assertIn("literature_facts", formatted)
        self.assertIn("citation_map", formatted)
        self.assertIn("knowledge_gaps", formatted)
        self.assertIn("final_hypothesis", formatted)
        self.assertIn("experiment_design", formatted)
        self.assertIn("small_validation", formatted)
    
    def test_validate_and_normalize_result(self):
        """测试验证和标准化结果"""
        # 测试完整结果
        complete_result = {
            "title": "测试报告",
            "paper_title": "测试论文",
            "paper_abstract": "摘要...",
            "markdown_content": "# 测试...",
            "chapters": {
                "problem_statement": "问题...",
                "rationale": "原理...",
                "technical_details": "技术...",
                "datasets": "数据...",
                "source": "源...",
                "target": "目标...",
                "methods": "方法...",
                "experiments": "实验...",
                "results": "结果...",
                "references": ["文献1", "文献2"]
            }
        }
        
        result = self.agent._validate_and_normalize_result(complete_result)
        
        # 验证所有字段都存在
        self.assertIn("title", result)
        self.assertIn("paper_title", result)
        self.assertIn("paper_abstract", result)
        self.assertIn("markdown_content", result)
        self.assertIn("chapters", result)
        
        # 验证所有章节都存在
        chapters = result["chapters"]
        required_chapters = [
            "problem_statement", "rationale", "technical_details",
            "datasets", "source", "target", "methods", "experiments", "results", "references"
        ]
        for chapter in required_chapters:
            self.assertIn(chapter, chapters)
        
        # 测试缺失字段的情况
        incomplete_result = {"title": "测试报告"}
        result = self.agent._validate_and_normalize_result(incomplete_result)
        
        # 验证缺失字段被补全
        self.assertIn("paper_title", result)
        self.assertIn("paper_abstract", result)
        self.assertIn("markdown_content", result)
        self.assertIn("chapters", result)
    
    @patch("app.agents.report_generation_agent.qwen_structured_chat")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_generate_report_success(
        self,
        mock_file,
        mock_makedirs,
        mock_qwen
    ):
        """测试生成报告成功"""
        project_info = {"title": "混合模型研究项目"}
        
        # 模拟 LLM 返回
        mock_qwen_result = {
            "title": "科学假设与研究计划",
            "paper_title": "基于混合 CNN-Transformer 模型的医学图像分类研究",
            "paper_abstract": "本文提出一种混合 CNN-Transformer 模型...",
            "markdown_content": "# 科学假设与研究计划...",
            "chapters": {
                "problem_statement": "医学图像分类是...",
                "rationale": "CNN 擅长提取...",
                "technical_details": "模型架构包括...",
                "datasets": "使用 ChestX-ray14 数据集...",
                "source": "源数据为 224x224 像素的 RGB 图像...",
                "target": "目标是输出 14 种疾病的概率分布...",
                "methods": "使用对比实验...",
                "experiments": "实验分为 3 组...",
                "results": "预期混合模型在 AUC 上提升 5-8%...",
                "references": [
                    "Wang, X., et al. (2017). ChestX-ray8: Hospital-scale Chest X-ray Database...",
                    "He, K., et al. (2016). Deep Residual Learning for Image Recognition..."
                ]
            }
        }
        
        mock_qwen.return_value = mock_qwen_result
        
        # 调用生成报告
        result = self.agent.generate_report(
            project_info=project_info,
            problem_understanding={"problem": "医学图像分类问题"},
            literature_facts=[{"content": "CNN 适合图像特征提取"}],
            citation_map=[{"source": "文献1"}],
            knowledge_gaps={"gaps": ["混合模型研究不足"]},
            final_hypothesis={"hypothesis": "混合模型优于单一模型"},
            experiment_design={"methods": "对比实验"},
            small_validation={"result": "初步验证成功"}
        )
        
        # 验证
        self.assertIsNotNone(result)
        self.assertIn("title", result)
        self.assertIn("paper_title", result)
        self.assertIn("paper_abstract", result)
        self.assertIn("markdown_content", result)
        self.assertIn("chapters", result)
        
        # 验证参考文献不是空的
        chapters = result["chapters"]
        self.assertTrue(len(chapters["references"]) > 0)
        
        mock_qwen.assert_called_once()
        mock_makedirs.assert_called()


if __name__ == '__main__':
    unittest.main()
