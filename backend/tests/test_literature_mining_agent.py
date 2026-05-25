"""
LiteratureMiningAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.agents.literature_mining_agent import (
    LiteratureMiningAgent,
    LiteratureMiningRequest,
    LiteratureMiningResponse,
    LITERATURE_MINING_PROMPT_TEMPLATE
)


class TestLiteratureMiningAgent(TestCase):
    """LiteratureMiningAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = LiteratureMiningAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("每条事实必须绑定来源信息", LITERATURE_MINING_PROMPT_TEMPLATE)
        self.assertIn("chunk_id", LITERATURE_MINING_PROMPT_TEMPLATE)
        self.assertIn("论文标题", LITERATURE_MINING_PROMPT_TEMPLATE)
        self.assertIn("页码", LITERATURE_MINING_PROMPT_TEMPLATE)
        self.assertIn("禁止编造无来源的事实", LITERATURE_MINING_PROMPT_TEMPLATE)
    
    def test_empty_response(self):
        """测试空响应"""
        response = self.agent._empty_response()
        
        self.assertIsInstance(response, LiteratureMiningResponse)
        self.assertEqual(len(response.facts), 0)
        self.assertEqual(len(response.evidence), 0)
        self.assertEqual(len(response.source_papers), 0)
        self.assertEqual(len(response.citation_map), 0)
        self.assertGreater(len(response.uncertain_points), 0)
    
    def test_format_chunks(self):
        """测试格式化文献片段"""
        # 模拟搜索结果
        mock_search_results = [
            MagicMock(
                chunk_id="chunk_001",
                content="这是第一个文献片段的内容",
                document_title="论文A",
                document_filename="paper_a.pdf",
                start_page=10,
                end_page=15,
                similarity=0.95
            ),
            MagicMock(
                chunk_id="chunk_002",
                content="这是第二个文献片段的内容",
                document_title="论文B",
                document_filename="paper_b.pdf",
                start_page=None,
                end_page=None,
                similarity=0.85
            )
        ]
        
        # 调用格式化
        result = self.agent._format_chunks(mock_search_results)
        
        # 验证
        self.assertIn("chunk_001", result)
        self.assertIn("论文A", result)
        self.assertIn("页 10", result)
        self.assertIn("chunk_002", result)
        self.assertIn("论文B", result)
    
    def test_validate_and_normalize(self):
        """测试结果验证和标准化"""
        # 正常情况
        valid_result = {
            "facts": [
                {
                    "fact_id": "fact_001",
                    "content": "测试事实",
                    "source_chunk_id": "chunk_001",
                    "source_paper_title": "论文A",
                    "source_page": 10
                }
            ],
            "evidence": [],
            "source_papers": ["论文A"],
            "citation_map": [],
            "uncertain_points": []
        }
        
        mock_search_results = [MagicMock(chunk_id="chunk_001")]
        
        response = self.agent._validate_and_normalize(valid_result, mock_search_results)
        
        self.assertIsInstance(response, LiteratureMiningResponse)
        self.assertEqual(len(response.facts), 1)
        self.assertEqual(response.facts[0].content, "测试事实")
        self.assertEqual(response.facts[0].source_chunk_id, "chunk_001")
    
    def test_validate_and_normalize_missing_source(self):
        """测试缺少来源信息的处理"""
        # 事实缺少 source_chunk_id
        incomplete_result = {
            "facts": [
                {
                    "fact_id": "fact_001",
                    "content": "测试事实",
                    "source_paper_title": "论文A"
                },
                {
                    "fact_id": "fact_002",
                    "content": "另一个事实",
                    "source_chunk_id": "chunk_002",
                    "source_paper_title": "论文B",
                    "source_page": 20
                }
            ],
            "evidence": [],
            "source_papers": [],
            "citation_map": [],
            "uncertain_points": []
        }
        
        mock_search_results = [
            MagicMock(chunk_id="chunk_001"),
            MagicMock(chunk_id="chunk_002")
        ]
        
        response = self.agent._validate_and_normalize(incomplete_result, mock_search_results)
        
        # 缺少 source_chunk_id 的事实应该被过滤掉
        self.assertEqual(len(response.facts), 1)
        self.assertEqual(response.facts[0].fact_id, "fact_002")
    
    def test_validate_and_normalize_missing_fields(self):
        """测试缺少字段时的标准化"""
        incomplete_result = {
            "facts": []
        }
        
        mock_search_results = []
        
        response = self.agent._validate_and_normalize(incomplete_result, mock_search_results)
        
        self.assertIsInstance(response, LiteratureMiningResponse)
        self.assertEqual(response.facts, [])
        self.assertEqual(response.evidence, [])
        self.assertEqual(response.source_papers, [])
        self.assertEqual(response.citation_map, [])
        self.assertEqual(response.uncertain_points, [])
    
    @patch('app.agents.literature_mining_agent.search_vector_store')
    @patch('app.agents.literature_mining_agent.qwen_structured_chat')
    def test_mine_success(self, mock_qwen, mock_search):
        """测试 mine 成功"""
        # 模拟搜索结果
        mock_search_results = [
            MagicMock(
                chunk_id="chunk_001",
                content="这是一个文献片段的内容，包含重要的科学事实",
                document_title="论文A",
                start_page=10,
                similarity=0.95
            )
        ]
        mock_search.return_value = mock_search_results
        
        # 模拟 Qwen 返回
        mock_qwen_result = {
            "facts": [
                {
                    "fact_id": "fact_001",
                    "content": "重要的科学事实内容",
                    "source_chunk_id": "chunk_001",
                    "source_paper_title": "论文A",
                    "source_page": 10
                }
            ],
            "evidence": [
                {
                    "evidence_id": "ev_001",
                    "fact_id": "fact_001",
                    "text": "证据原文",
                    "source_chunk_id": "chunk_001"
                }
            ],
            "source_papers": ["论文A"],
            "citation_map": [
                {
                    "paper_title": "论文A",
                    "fact_ids": ["fact_001"],
                    "chunk_ids": ["chunk_001"]
                }
            ],
            "uncertain_points": ["某些观点需要进一步验证"]
        }
        mock_qwen.return_value = mock_qwen_result
        
        # 调用挖掘
        response = self.agent.mine(
            project_id="project-123",
            research_question="测试研究问题",
            top_k=10
        )
        
        # 验证
        self.assertIsInstance(response, LiteratureMiningResponse)
        self.assertEqual(len(response.facts), 1)
        self.assertEqual(response.facts[0].source_chunk_id, "chunk_001")
        mock_search.assert_called_once()
        mock_qwen.assert_called_once()
    
    @patch('app.agents.literature_mining_agent.search_vector_store')
    def test_mine_no_results(self, mock_search):
        """测试没有搜索结果时的处理"""
        mock_search.return_value = []
        
        response = self.agent.mine(
            project_id="project-123",
            research_question="测试研究问题",
            top_k=10
        )
        
        self.assertIsInstance(response, LiteratureMiningResponse)
        self.assertEqual(len(response.facts), 0)
        self.assertIn("未找到相关文献片段", response.uncertain_points)


if __name__ == '__main__':
    unittest.main()
