"""
HypothesisGenerationAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.agents.hypothesis_generation_agent import (
    HypothesisGenerationAgent,
    HypothesisItem,
    HypothesisGenerationResult,
    HYPOTHESIS_GENERATION_PROMPT_TEMPLATE
)


class TestHypothesisGenerationAgent(TestCase):
    """HypothesisGenerationAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = HypothesisGenerationAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("归纳推理", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("演绎推理", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("避免空泛套话", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("hypothesis", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("rationale", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("novelty", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("testability", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("required_data", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("possible_method", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
        self.assertIn("risk", HYPOTHESIS_GENERATION_PROMPT_TEMPLATE)
    
    def test_format_facts(self):
        """测试格式化事实"""
        test_facts = [
            {
                "content": "事实 1 内容",
                "source_paper_title": "来源论文 A"
            },
            {
                "content": "事实 2 内容",
                "source_paper_title": ""
            }
        ]
        
        result = self.agent._format_facts(test_facts)
        
        self.assertIn("事实 1 内容", result)
        self.assertIn("来源论文 A", result)
        self.assertIn("事实 2 内容", result)
    
    def test_format_gaps(self):
        """测试格式化知识缺口"""
        test_gaps = [
            {
                "description": "知识缺口 1 描述",
                "potential_value": "研究价值描述"
            },
            {
                "description": "知识缺口 2 描述",
                "potential_value": ""
            }
        ]
        
        result = self.agent._format_gaps(test_gaps)
        
        self.assertIn("知识缺口 1 描述", result)
        self.assertIn("研究价值描述", result)
        self.assertIn("知识缺口 2 描述", result)
    
    def test_format_constraints(self):
        """测试格式化约束条件"""
        test_constraints = ["约束 1", "约束 2", "约束 3"]
        
        result = self.agent._format_constraints(test_constraints)
        
        self.assertIn("约束 1", result)
        self.assertIn("约束 2", result)
        self.assertIn("约束 3", result)
    
    def test_validate_and_normalize_result(self):
        """测试验证和标准化结果"""
        # 正常情况
        valid_result = {
            "hypotheses": [
                {
                    "hypothesis": "假设 1",
                    "rationale": "理由 1",
                    "novelty": "创新点 1",
                    "testability": "可测试性 1",
                    "required_data": "所需数据 1",
                    "possible_method": "可能的方法 1",
                    "risk": "风险 1"
                },
                {
                    "hypothesis": "假设 2",
                    "rationale": "理由 2",
                    "novelty": "创新点 2",
                    "testability": "可测试性 2",
                    "required_data": "所需数据 2",
                    "possible_method": "可能的方法 2",
                    "risk": "风险 2"
                },
                {
                    "hypothesis": "假设 3",
                    "rationale": "理由 3",
                    "novelty": "创新点 3",
                    "testability": "可测试性 3",
                    "required_data": "所需数据 3",
                    "possible_method": "可能的方法 3",
                    "risk": "风险 3"
                }
            ],
            "summary": "测试摘要"
        }
        
        result = self.agent._validate_and_normalize_result(valid_result)
        
        self.assertIsInstance(result, HypothesisGenerationResult)
        self.assertEqual(len(result.hypotheses), 3)
        self.assertEqual(result.summary, "测试摘要")
    
    def test_validate_and_normalize_result_missing_fields(self):
        """测试缺少字段的情况"""
        incomplete_result = {
            "hypotheses": [
                {
                    "hypothesis": "只有假设",
                    "rationale": ""
                }
            ]
        }
        
        result = self.agent._validate_and_normalize_result(incomplete_result)
        
        self.assertEqual(len(result.hypotheses), 1)
        self.assertEqual(result.hypotheses[0].hypothesis, "只有假设")
        # 其他字段应该为空字符串
        self.assertEqual(result.hypotheses[0].novelty, "")
    
    def test_validate_and_normalize_result_too_many(self):
        """测试超过 5 条的情况"""
        many_hypotheses = []
        for i in range(7):
            many_hypotheses.append({
                "hypothesis": f"假设 {i+1}",
                "rationale": f"理由 {i+1}",
                "novelty": f"创新点 {i+1}",
                "testability": f"可测试性 {i+1}",
                "required_data": f"所需数据 {i+1}",
                "possible_method": f"可能的方法 {i+1}",
                "risk": f"风险 {i+1}"
            })
        
        result_dict = {"hypotheses": many_hypotheses}
        result = self.agent._validate_and_normalize_result(result_dict)
        
        # 应该截断为 5 条
        self.assertEqual(len(result.hypotheses), 5)
    
    @patch('app.agents.hypothesis_generation_agent.qwen_structured_chat')
    def test_generate_success(self, mock_qwen):
        """测试 generate 成功"""
        # 测试数据
        test_research_question = "机器学习在医学影像中的应用效果如何？"
        test_facts = [
            {
                "content": "卷积神经网络在医学影像分类中表现优异",
                "source_paper_title": "深度学习医学影像综述"
            }
        ]
        test_gaps = [
            {
                "description": "缺乏 CNN 与 Transformer 的对比研究",
                "potential_value": "帮助选择更合适的模型"
            }
        ]
        test_constraints = ["计算资源有限", "需要在 3 个月内完成"]
        
        # 模拟 LLM 返回
        mock_qwen_result = {
            "hypotheses": [
                {
                    "hypothesis": "混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
                    "rationale": "基于归纳推理：CNN 提取空间特征，Transformer 处理长距离依赖，两者结合可以互补",
                    "novelty": "首次系统对比三种模型架构在特定医学影像任务上的性能",
                    "testability": "可以通过构建三个模型，在相同数据集上进行训练和测试，对比准确率、召回率等指标",
                    "required_data": "公开医学影像数据集（如 ChestX-ray14），标注数据",
                    "possible_method": "实现三个模型：纯 CNN、纯 Transformer、混合模型，进行对比实验",
                    "risk": "混合模型可能计算复杂度高，训练时间长，可能存在过拟合风险"
                },
                {
                    "hypothesis": "数据增强技术可以显著提升小数据集上的模型性能",
                    "rationale": "基于演绎推理：现有研究表明数据增强在图像任务中有效，医学影像数据通常较少",
                    "novelty": "专门针对医学影像设计数据增强策略",
                    "testability": "可以通过对比有/无数据增强的模型性能来验证",
                    "required_data": "医学影像数据集，包含训练、验证、测试集",
                    "possible_method": "设计多种数据增强策略（旋转、翻转、缩放等），进行 ablation study",
                    "risk": "过度增强可能导致数据失真，引入噪声"
                },
                {
                    "hypothesis": "迁移学习在医学影像任务中比从零训练更有效",
                    "rationale": "基于归纳推理：在自然图像上预训练的模型已经学到通用特征，迁移到医学影像可以提升性能",
                    "novelty": "对比不同预训练策略在医学影像上的效果",
                    "testability": "可以对比从零训练、使用 ImageNet 预训练、使用医学影像预训练三种策略",
                    "required_data": "医学影像数据集，预训练模型权重",
                    "possible_method": "实现三种训练策略，对比收敛速度和最终性能",
                    "risk": "自然图像预训练的模型可能不适合医学影像的特征分布"
                }
            ],
            "summary": "生成了 3 条科学假设，涵盖模型架构、数据增强和迁移学习三个方向"
        }
        
        mock_qwen.return_value = mock_qwen_result
        
        # 调用 generate
        result = self.agent.generate(
            research_question=test_research_question,
            facts=test_facts,
            knowledge_gaps=test_gaps,
            constraints=test_constraints
        )
        
        # 验证
        self.assertIsInstance(result, HypothesisGenerationResult)
        self.assertEqual(len(result.hypotheses), 3)
        
        # 验证第一条假设的结构
        hypo = result.hypotheses[0]
        self.assertIsInstance(hypo, HypothesisItem)
        self.assertTrue(len(hypo.hypothesis) > 0)
        self.assertTrue(len(hypo.rationale) > 0)
        self.assertTrue(len(hypo.novelty) > 0)
        self.assertTrue(len(hypo.testability) > 0)
        self.assertTrue(len(hypo.required_data) > 0)
        self.assertTrue(len(hypo.possible_method) > 0)
        self.assertTrue(len(hypo.risk) > 0)
        
        mock_qwen.assert_called_once()


if __name__ == '__main__':
    unittest.main()
