"""
HypothesisReviewAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.agents.hypothesis_review_agent import (
    HypothesisReviewAgent,
    HypothesisCandidate,
    HypothesisReviewRequest,
    HYPOTHESIS_REVIEW_PROMPT_TEMPLATE
)


class TestHypothesisReviewAgent(TestCase):
    """HypothesisReviewAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = HypothesisReviewAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("scientific_value", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("novelty", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("testability", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("data_availability", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("cost_risk", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("评分理由必须具体", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("指出低分原因", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
        self.assertIn("按综合得分从高到低排序", HYPOTHESIS_REVIEW_PROMPT_TEMPLATE)
    
    def test_format_hypotheses(self):
        """测试格式化假设列表"""
        test_hypotheses = [
            HypothesisCandidate(
                hypothesis="混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
                rationale="CNN 提取空间特征，Transformer 处理长距离依赖",
                testability="可以通过对比实验验证"
            ),
            HypothesisCandidate(
                hypothesis="数据增强技术可以显著提升小数据集上的模型性能",
                required_data="公开医学影像数据集"
            )
        ]
        
        result = self.agent._format_hypotheses(test_hypotheses)
        
        # 验证包含关键信息
        self.assertIn("混合 CNN-Transformer 模型", result)
        self.assertIn("数据增强技术", result)
        self.assertIn("假设 0", result)
        self.assertIn("假设 1", result)
    
    def test_create_default_scores(self):
        """测试创建默认评分"""
        scores = self.agent._create_default_scores()
        
        # 验证包含所有 5 个维度
        self.assertIn("scientific_value", scores)
        self.assertIn("novelty", scores)
        self.assertIn("testability", scores)
        self.assertIn("data_availability", scores)
        self.assertIn("cost_risk", scores)
        
        # 验证默认值正确
        for key, score in scores.items():
            self.assertEqual(score["score"], 5)
            self.assertIsNotNone(score["reason"])
    
    def test_validate_and_normalize_result(self):
        """测试验证和标准化结果"""
        test_hypotheses = [
            HypothesisCandidate(hypothesis="测试假设 1"),
            HypothesisCandidate(hypothesis="测试假设 2"),
            HypothesisCandidate(hypothesis="测试假设 3")
        ]
        
        # 模拟一个包含不同得分的结果
        result_dict = {
            "reviews": [
                {
                    "hypothesis_index": 0,
                    "hypothesis": "测试假设 1",
                    "scores": {
                        "scientific_value": {"score": 8, "reason": "很好", "low_score_reason": None},
                        "novelty": {"score": 9, "reason": "优秀", "low_score_reason": None},
                        "testability": {"score": 7, "reason": "较好", "low_score_reason": None},
                        "data_availability": {"score": 6, "reason": "一般", "low_score_reason": None},
                        "cost_risk": {"score": 5, "reason": "中等", "low_score_reason": "成本较高"}
                    },
                    "overall_score": 7.0,
                    "suggestions": "建议改进",
                    "strengths": ["科学价值高"],
                    "weaknesses": ["成本高"]
                },
                {
                    "hypothesis_index": 1,
                    "hypothesis": "测试假设 2",
                    "scores": {
                        "scientific_value": {"score": 6, "reason": "一般", "low_score_reason": None},
                        "novelty": {"score": 7, "reason": "较好", "low_score_reason": None},
                        "testability": {"score": 8, "reason": "很好", "low_score_reason": None},
                        "data_availability": {"score": 9, "reason": "优秀", "low_score_reason": None},
                        "cost_risk": {"score": 6, "reason": "一般", "low_score_reason": None}
                    },
                    "overall_score": 7.2,  # 这个得分更高，应该排在前面
                    "suggestions": "建议继续",
                    "strengths": ["数据易获取"],
                    "weaknesses": ["创新性一般"]
                },
                {
                    "hypothesis_index": 2,
                    # 缺少一些字段，测试补全
                    "hypothesis": "测试假设 3"
                }
            ],
            "summary": "总体评价"
        }
        
        result = self.agent._validate_and_normalize_result(
            result_dict, test_hypotheses
        )
        
        # 验证排序正确（第二条得分更高，应该排在第一位）
        self.assertEqual(len(result.reviews), 3)
        self.assertEqual(result.reviews[0].overall_score, 7.2)
        self.assertEqual(result.reviews[0].hypothesis_index, 1)
        self.assertEqual(result.reviews[1].overall_score, 7.0)
        self.assertEqual(result.reviews[1].hypothesis_index, 0)
        
        # 验证第三条被正确补全
        self.assertIsNotNone(result.reviews[2].scores)
        self.assertIsNotNone(result.reviews[2].overall_score)
        
        # 验证 summary 正确
        self.assertEqual(result.summary, "总体评价")
    
    @patch('app.agents.hypothesis_review_agent.qwen_structured_chat')
    def test_review_success(self, mock_qwen):
        """测试 review 成功"""
        test_hypotheses = [
            HypothesisCandidate(
                hypothesis="混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
                rationale="基于归纳推理：CNN 提取空间特征，Transformer 处理长距离依赖",
                novelty="首次系统对比三种模型架构",
                testability="可以通过对比实验验证",
                required_data="公开医学影像数据集",
                possible_method="实现三个模型进行对比",
                risk="混合模型可能计算复杂度高"
            ),
            HypothesisCandidate(
                hypothesis="数据增强技术可以显著提升小数据集上的模型性能",
                rationale="数据增强在图像任务中有效，医学影像数据通常较少",
                testability="可以通过对比有/无数据增强的性能验证",
                required_data="医学影像数据集",
                possible_method="设计多种数据增强策略"
            )
        ]
        
        # 模拟 LLM 返回
        mock_qwen_result = {
            "reviews": [
                {
                    "hypothesis_index": 0,
                    "hypothesis": "混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
                    "scores": {
                        "scientific_value": {
                            "score": 8,
                            "reason": "该假设针对医学影像领域核心问题，若验证成功将显著推动模型架构发展",
                            "low_score_reason": None
                        },
                        "novelty": {
                            "score": 9,
                            "reason": "首次系统对比三种架构在特定任务上的性能，创新点明确",
                            "low_score_reason": None
                        },
                        "testability": {
                            "score": 7,
                            "reason": "实验设计清晰，可以通过对照实验验证，但需要较大计算资源",
                            "low_score_reason": None
                        },
                        "data_availability": {
                            "score": 6,
                            "reason": "公开数据集可用，但特定医学影像数据获取可能受限",
                            "low_score_reason": "可能需要机构合作获取数据"
                        },
                        "cost_risk": {
                            "score": 5,
                            "reason": "实验成本较高，训练时间较长，存在模型不收敛风险",
                            "low_score_reason": "计算资源消耗大，周期可能超预期"
                        }
                    },
                    "overall_score": 7.0,
                    "suggestions": "1. 建议先进行小规模预实验验证可行性；2. 考虑使用预训练模型降低计算成本；3. 设计更高效的混合架构；4. 提前规划数据获取方案",
                    "strengths": ["创新性强", "科学价值高", "实验设计清晰"],
                    "weaknesses": ["成本风险较高", "数据获取可能受限"]
                },
                {
                    "hypothesis_index": 1,
                    "hypothesis": "数据增强技术可以显著提升小数据集上的模型性能",
                    "scores": {
                        "scientific_value": {
                            "score": 6,
                            "reason": "该问题研究较多，但针对医学影像的系统性研究仍有价值",
                            "low_score_reason": None
                        },
                        "novelty": {
                            "score": 5,
                            "reason": "数据增强概念较成熟，需要更具体的创新点",
                            "low_score_reason": "创新性不足，建议提出更有针对性的增强策略"
                        },
                        "testability": {
                            "score": 9,
                            "reason": "实验设计非常简单，易于快速验证",
                            "low_score_reason": None
                        },
                        "data_availability": {
                            "score": 8,
                            "reason": "公开医学影像数据集充足，易于获取",
                            "low_score_reason": None
                        },
                        "cost_risk": {
                            "score": 8,
                            "reason": "实验成本低，周期短，风险可控",
                            "low_score_reason": None
                        }
                    },
                    "overall_score": 7.2,
                    "suggestions": "1. 建议聚焦于医学影像特定的增强策略；2. 增加消融实验分析不同增强方法的效果；3. 可以与第一个假设结合，探索数据增强对混合模型的影响",
                    "strengths": ["可测试性强", "数据易获取", "成本低风险小"],
                    "weaknesses": ["创新性一般"]
                }
            ],
            "summary": "共评审 2 条假设，建议优先考虑第二条假设进行快速验证，同时投入资源完善第一条假设的实验设计。两条假设可以结合开展研究。"
        }
        
        mock_qwen.return_value = mock_qwen_result
        
        # 调用 review
        result = self.agent.review(hypotheses=test_hypotheses)
        
        # 验证
        self.assertIsNotNone(result)
        self.assertEqual(len(result.reviews), 2)
        self.assertIsNotNone(result.summary)
        
        # 验证排序正确（第二条得分更高）
        self.assertEqual(result.reviews[0].hypothesis_index, 1)
        self.assertEqual(result.reviews[0].overall_score, 7.2)
        self.assertEqual(result.reviews[1].hypothesis_index, 0)
        self.assertEqual(result.reviews[1].overall_score, 7.0)
        
        # 验证评分详情
        review = result.reviews[0]
        self.assertIsNotNone(review.scores.scientific_value)
        self.assertIsNotNone(review.scores.novelty)
        self.assertIsNotNone(review.scores.testability)
        self.assertIsNotNone(review.scores.data_availability)
        self.assertIsNotNone(review.scores.cost_risk)
        self.assertEqual(len(review.suggestions) > 0, True)
        self.assertEqual(len(review.strengths) > 0, True)
        self.assertEqual(len(review.weaknesses) > 0, True)
        
        mock_qwen.assert_called_once()


if __name__ == '__main__':
    unittest.main()
