"""
ProblemUnderstandingAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.agents.problem_understanding_agent import (
    ProblemUnderstandingAgent,
    ProblemUnderstandingRequest,
    ProblemUnderstandingResponse,
    PROBLEM_UNDERSTANDING_PROMPT_TEMPLATE
)


class TestProblemUnderstandingAgent(TestCase):
    """ProblemUnderstandingAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = ProblemUnderstandingAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("明确研究问题", PROBLEM_UNDERSTANDING_PROMPT_TEMPLATE)
        self.assertIn("边界定义", PROBLEM_UNDERSTANDING_PROMPT_TEMPLATE)
        self.assertIn("避免泛化", PROBLEM_UNDERSTANDING_PROMPT_TEMPLATE)
    
    def test_build_prompt(self):
        """测试 Prompt 构建"""
        research_question = "如何利用机器学习？"
        domain_description = "人工智能"
        
        prompt = self.agent._build_prompt(research_question, domain_description)
        
        self.assertIn(research_question, prompt)
        self.assertIn(domain_description, prompt)
    
    def test_build_prompt_without_domain(self):
        """测试没有领域描述时的 Prompt 构建"""
        research_question = "如何利用机器学习？"
        
        prompt = self.agent._build_prompt(research_question, None)
        
        self.assertIn(research_question, prompt)
        self.assertIn("未指定", prompt)
    
    def test_validate_and_normalize(self):
        """测试结果验证和标准化"""
        # 正常情况
        valid_result = {
            "problem_statement": "测试问题陈述",
            "research_domain": "测试领域",
            "keywords": ["关键词1", "关键词2"],
            "scope_boundary": "测试边界",
            "constraints": ["约束1", "约束2"],
            "expected_output": ["输出1", "输出2"]
        }
        
        response = self.agent._validate_and_normalize(valid_result)
        
        self.assertIsInstance(response, ProblemUnderstandingResponse)
        self.assertEqual(response.problem_statement, "测试问题陈述")
        self.assertEqual(response.research_domain, "测试领域")
        self.assertEqual(len(response.keywords), 2)
    
    def test_validate_and_normalize_missing_fields(self):
        """测试缺少字段时的标准化"""
        incomplete_result = {
            "problem_statement": "测试问题陈述"
        }
        
        response = self.agent._validate_and_normalize(incomplete_result)
        
        self.assertIsInstance(response, ProblemUnderstandingResponse)
        self.assertEqual(response.problem_statement, "测试问题陈述")
        self.assertEqual(response.research_domain, "")
        self.assertEqual(response.keywords, [])
    
    def test_validate_and_normalize_wrong_types(self):
        """测试字段类型错误时的标准化"""
        wrong_type_result = {
            "problem_statement": "测试问题陈述",
            "research_domain": "测试领域",
            "keywords": "不是列表",
            "scope_boundary": "测试边界",
            "constraints": "不是列表",
            "expected_output": "不是列表"
        }
        
        response = self.agent._validate_and_normalize(wrong_type_result)
        
        self.assertIsInstance(response, ProblemUnderstandingResponse)
        self.assertEqual(response.keywords, [])
        self.assertEqual(response.constraints, [])
        self.assertEqual(response.expected_output, [])
    
    @patch('app.agents.problem_understanding_agent.qwen_structured_chat')
    def test_analyze_success(self, mock_qwen):
        """测试 analyze 成功"""
        # 模拟 Qwen 返回
        mock_result = {
            "problem_statement": "如何利用机器学习提高医学影像诊断的准确率，特别是在肿瘤检测方面的应用研究",
            "research_domain": "医学人工智能",
            "keywords": ["机器学习", "医学影像", "肿瘤检测", "诊断准确率"],
            "scope_boundary": "本研究聚焦于利用机器学习算法提高胸部CT影像中肺癌结节检测的准确率，不包括其他疾病或影像模态的研究",
            "constraints": ["需要有标注的医学影像数据", "算法性能需要达到临床可用水平"],
            "expected_output": ["改进的检测算法", "性能评估报告", "开源代码"]
        }
        
        mock_qwen.return_value = mock_result
        
        # 调用分析
        response = self.agent.analyze(
            research_question="如何利用机器学习提高医学影像诊断的准确率？",
            domain_description="医学影像、人工智能、深度学习"
        )
        
        # 验证
        self.assertIsInstance(response, ProblemUnderstandingResponse)
        self.assertEqual(response.problem_statement, mock_result["problem_statement"])
        mock_qwen.assert_called_once()


if __name__ == '__main__':
    unittest.main()
