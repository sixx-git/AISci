"""
KnowledgeGapAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.agents.knowledge_gap_agent import (
    KnowledgeGapAgent,
    KnowledgeGapRequest,
    KnowledgeGapResponse,
    KNOWLEDGE_GAP_PROMPT_TEMPLATE
)
from app.agents.literature_mining_agent import ScienceFact


class TestKnowledgeGapAgent(TestCase):
    """KnowledgeGapAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = KnowledgeGapAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("每个知识缺口都必须说明依据", KNOWLEDGE_GAP_PROMPT_TEMPLATE)
        self.assertIn("每个知识缺口都需要说明可能的研究价值", KNOWLEDGE_GAP_PROMPT_TEMPLATE)
        self.assertIn("识别文献之间的矛盾和不一致", KNOWLEDGE_GAP_PROMPT_TEMPLATE)
        self.assertIn("发现不同事实之间可能的潜在联系", KNOWLEDGE_GAP_PROMPT_TEMPLATE)
        self.assertIn("提出有前景的研究机会", KNOWLEDGE_GAP_PROMPT_TEMPLATE)
    
    def test_empty_response(self):
        """测试空响应"""
        response = self.agent._empty_response()
        
        self.assertIsInstance(response, KnowledgeGapResponse)
        self.assertEqual(len(response.known_facts), 0)
        self.assertEqual(len(response.knowledge_gaps), 0)
        self.assertEqual(len(response.contradictions), 0)
        self.assertEqual(len(response.possible_connections), 0)
        self.assertEqual(len(response.research_opportunities), 0)
    
    def test_format_facts(self):
        """测试格式化科学事实"""
        # 创建测试事实
        test_facts = [
            ScienceFact(
                fact_id="fact_001",
                content="卷积神经网络在医学影像分类中表现优异",
                source_chunk_id="chunk_123",
                source_paper_title="深度学习医学影像综述",
                source_page=10
            ),
            ScienceFact(
                fact_id="fact_002",
                content="Transformer 模型在自然语言处理中有广泛应用",
                source_chunk_id="chunk_456",
                source_paper_title="NLP 技术进展",
                source_page=20
            )
        ]
        
        # 调用格式化
        result = self.agent._format_facts(test_facts)
        
        # 验证
        self.assertIn("fact_001", result)
        self.assertIn("卷积神经网络", result)
        self.assertIn("深度学习医学影像综述", result)
        self.assertIn("fact_002", result)
        self.assertIn("Transformer", result)
    
    def test_format_uncertain(self):
        """测试格式化不确定的点"""
        test_uncertain = [
            "不同数据集的性能差异较大",
            "模型泛化能力需要进一步验证"
        ]
        
        result = self.agent._format_uncertain(test_uncertain)
        
        self.assertIn("不同数据集的性能差异较大", result)
        self.assertIn("模型泛化能力需要进一步验证", result)
    
    def test_validate_and_normalize(self):
        """测试结果验证和标准化"""
        # 正常情况
        valid_result = {
            "known_facts": [
                {
                    "fact_id": "fact_001",
                    "content": "测试事实",
                    "source_paper_title": "测试论文"
                }
            ],
            "knowledge_gaps": [
                {
                    "gap_id": "gap_001",
                    "description": "测试缺口",
                    "basis": ["fact_001"],
                    "potential_value": "测试价值"
                }
            ],
            "contradictions": [],
            "possible_connections": [],
            "research_opportunities": []
        }
        
        test_facts = [
            ScienceFact(
                fact_id="fact_001",
                content="测试事实",
                source_chunk_id="chunk_123"
            )
        ]
        
        response = self.agent._validate_and_normalize(valid_result, test_facts)
        
        self.assertIsInstance(response, KnowledgeGapResponse)
        self.assertEqual(len(response.known_facts), 1)
        self.assertEqual(len(response.knowledge_gaps), 1)
    
    def test_validate_and_normalize_missing_basis(self):
        """测试缺少依据时的标准化"""
        incomplete_result = {
            "known_facts": [],
            "knowledge_gaps": [
                {
                    "gap_id": "gap_001",
                    "description": "测试缺口",
                    "potential_value": "测试价值"
                }
            ],
            "contradictions": [],
            "possible_connections": [],
            "research_opportunities": []
        }
        
        response = self.agent._validate_and_normalize(incomplete_result, [])
        
        self.assertEqual(len(response.knowledge_gaps), 1)
        self.assertEqual(response.knowledge_gaps[0].basis, [])
    
    def test_validate_and_normalize_confidence(self):
        """测试置信度标准化"""
        test_result = {
            "known_facts": [],
            "knowledge_gaps": [],
            "contradictions": [],
            "possible_connections": [
                {
                    "connection_id": "connect_001",
                    "fact_ids": ["fact_001"],
                    "description": "测试联系",
                    "confidence": "high"  # 非数值
                }
            ],
            "research_opportunities": [
                {
                    "opportunity_id": "opp_001",
                    "title": "测试机会",
                    "description": "测试描述",
                    "related_gap_ids": [],
                    "expected_impact": "高",
                    "feasibility": "中等"  # 非数值
                }
            ]
        }
        
        response = self.agent._validate_and_normalize(test_result, [])
        
        self.assertEqual(response.possible_connections[0].confidence, 0.5)
        self.assertEqual(response.research_opportunities[0].feasibility, 0.5)
    
    @patch('app.agents.knowledge_gap_agent.qwen_structured_chat')
    def test_analyze_success(self, mock_qwen):
        """测试 analyze 成功"""
        # 测试事实
        test_facts = [
            ScienceFact(
                fact_id="fact_001",
                content="卷积神经网络在医学影像分类中表现优异",
                source_chunk_id="chunk_123",
                source_paper_title="深度学习医学影像综述",
                source_page=10
            ),
            ScienceFact(
                fact_id="fact_002",
                content="Transformer 模型在序列数据处理中有优势",
                source_chunk_id="chunk_456",
                source_paper_title="NLP 技术进展",
                source_page=20
            )
        ]
        
        test_uncertain = [
            "不同模型在医学影像任务中的对比研究不足"
        ]
        
        # 模拟 Qwen 返回
        mock_qwen_result = {
            "known_facts": [
                {
                    "fact_id": "fact_001",
                    "content": "卷积神经网络在医学影像分类中表现优异",
                    "source_paper_title": "深度学习医学影像综述"
                }
            ],
            "knowledge_gaps": [
                {
                    "gap_id": "gap_001",
                    "description": "缺乏 CNN 与 Transformer 在医学影像任务的直接对比研究",
                    "basis": ["fact_001", "fact_002"],
                    "potential_value": "帮助研究者选择更合适的模型架构"
                }
            ],
            "contradictions": [],
            "possible_connections": [
                {
                    "connection_id": "connect_001",
                    "fact_ids": ["fact_001", "fact_002"],
                    "description": "可以探索将 Transformer 思想应用于医学影像任务",
                    "confidence": 0.7
                }
            ],
            "research_opportunities": [
                {
                    "opportunity_id": "opp_001",
                    "title": "混合 CNN-Transformer 模型在医学影像中的应用",
                    "description": "结合 CNN 的空间特征提取能力和 Transformer 的长距离依赖建模能力",
                    "related_gap_ids": ["gap_001"],
                    "expected_impact": "提升医学影像分析性能",
                    "feasibility": 0.8
                }
            ]
        }
        
        mock_qwen.return_value = mock_qwen_result
        
        # 调用 analyze
        response = self.agent.analyze(
            facts=test_facts,
            uncertain_points=test_uncertain
        )
        
        # 验证
        self.assertIsInstance(response, KnowledgeGapResponse)
        self.assertEqual(len(response.known_facts), 1)
        self.assertEqual(len(response.knowledge_gaps), 1)
        self.assertEqual(len(response.possible_connections), 1)
        self.assertEqual(len(response.research_opportunities), 1)
        
        # 验证知识缺口有依据和价值
        self.assertEqual(response.knowledge_gaps[0].gap_id, "gap_001")
        self.assertGreater(len(response.knowledge_gaps[0].basis), 0)
        self.assertTrue(len(response.knowledge_gaps[0].potential_value) > 0)
        
        mock_qwen.assert_called_once()


if __name__ == '__main__':
    unittest.main()
