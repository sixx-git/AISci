"""
所有 Agent 的 Mock 测试
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 导入所有 Agent
from app.agents.problem_understanding_agent import ProblemUnderstandingAgent
from app.agents.literature_mining_agent import LiteratureMiningAgent
from app.agents.knowledge_gap_agent import KnowledgeGapAgent
from app.agents.hypothesis_generation_agent import HypothesisGenerationAgent
from app.agents.hypothesis_review_agent import HypothesisReviewAgent
from app.agents.report_generation_agent import ReportGenerationAgent


@pytest.fixture
def mock_qwen_llm():
    """Mock Qwen LLM 服务"""
    with patch('app.agents.problem_understanding_agent.qwen_structured_chat') as mock:
        mock.return_value = {
            "problem_statement": "这是一个测试问题陈述",
            "research_domain": "城市气候学",
            "keywords": ["热岛效应", "城市绿化"],
            "scope_boundary": "研究边界",
            "constraints": ["数据限制", "时间限制"],
            "expected_output": ["研究报告", "实验设计"]
        }
        yield mock


@pytest.fixture
def mock_project():
    """Mock 项目对象"""
    project = Mock()
    project.id = "test_project_123"
    project.name = "Test Research Project"
    project.research_question = "城市绿化对热岛效应的影响是什么？"
    return project


@pytest.mark.agent
class TestProblemUnderstandingAgent:
    """问题理解 Agent 测试"""

    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = ProblemUnderstandingAgent()
        assert agent is not None
        assert hasattr(agent, '_build_prompt')
        assert hasattr(agent, '_validate_and_normalize')

    def test_prompt_building(self):
        """测试 Prompt 构建"""
        agent = ProblemUnderstandingAgent()
        prompt = agent._build_prompt(
            "城市绿化对热岛效应的影响是什么？",
            "城市气候研究"
        )
        
        assert isinstance(prompt, str)
        assert "城市绿化" in prompt
        assert "热岛效应" in prompt
        assert "城市气候研究" in prompt

    @patch('app.agents.problem_understanding_agent.qwen_structured_chat')
    def test_analyze_success(self, mock_qwen):
        """测试成功分析研究问题"""
        mock_qwen.return_value = {
            "problem_statement": "这是一个测试问题陈述",
            "research_domain": "城市气候学",
            "keywords": ["热岛效应", "城市绿化"],
            "scope_boundary": "研究边界",
            "constraints": ["数据限制", "时间限制"],
            "expected_output": ["研究报告", "实验设计"]
        }
        
        agent = ProblemUnderstandingAgent()
        response = agent.analyze(
            "城市绿化对热岛效应的影响是什么？",
            "城市气候研究"
        )
        
        assert response is not None
        assert response.problem_statement == "这是一个测试问题陈述"
        mock_qwen.assert_called()


@pytest.mark.agent
class TestLiteratureMiningAgent:
    """文献挖掘 Agent 测试"""

    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = LiteratureMiningAgent()
        assert agent is not None

    @patch('app.agents.literature_mining_agent.qwen_structured_chat')
    def test_mine_literature(self, mock_qwen):
        """测试文献挖掘"""
        mock_qwen.return_value = {
            "key_findings": [
                {"title": "研究1", "finding": "发现1", "source": "文献1"},
                {"title": "研究2", "finding": "发现2", "source": "文献2"}
            ],
            "methodologies": ["方法1", "方法2"],
            "theoretical_framework": "理论框架"
        }
        
        agent = LiteratureMiningAgent()
        response = agent.mine(
            "研究问题",
            [{"content": "文献内容", "source": "文献1"}]
        )
        
        assert response is not None
        assert hasattr(response, 'key_findings')
        assert len(response.key_findings) >= 2
        mock_qwen.assert_called()


@pytest.mark.agent
class TestKnowledgeGapAgent:
    """知识缺口 Agent 测试"""

    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = KnowledgeGapAgent()
        assert agent is not None

    @patch('app.agents.knowledge_gap_agent.qwen_structured_chat')
    def test_analyze_gaps(self, mock_qwen):
        """测试识别知识缺口"""
        mock_qwen.return_value = {
            "known_facts": [],
            "knowledge_gaps": [
                {
                    "gap_id": "gap_001",
                    "description": "尚未解决的新挑战：缺口描述1",
                    "basis": ["fact_001"],
                    "potential_value": "研究价值1",
                }
            ],
            "contradictions": [],
            "possible_connections": [],
            "research_opportunities": [],
        }
        
        agent = KnowledgeGapAgent()
        response = agent.analyze(
            facts=[],
            uncertain_points=[],
            research_question="测试研究问题",
            main_contradiction="主要矛盾",
        )
        
        assert response is not None
        assert len(response.knowledge_gaps) >= 1
        mock_qwen.assert_called()


@pytest.mark.agent
class TestHypothesisGenerationAgent:
    """假设生成 Agent 测试"""

    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = HypothesisGenerationAgent()
        assert agent is not None

    @patch('app.agents.hypothesis_generation_agent.qwen_structured_chat')
    def test_generate_hypotheses(self, mock_qwen):
        """测试生成假设"""
        mock_qwen.return_value = {
            "hypotheses": [
                {
                    "statement": "假设陈述1",
                    "rationale": "理由1",
                    "novelty_score": 8,
                    "feasibility_score": 7
                },
                {
                    "statement": "假设陈述2",
                    "rationale": "理由2",
                    "novelty_score": 7,
                    "feasibility_score": 8
                }
            ]
        }
        
        agent = HypothesisGenerationAgent()
        response = agent.generate("研究问题", [], [])
        
        assert response is not None
        assert len(response.hypotheses) >= 2
        mock_qwen.assert_called()


@pytest.mark.agent
class TestHypothesisReviewAgent:
    """假设评审 Agent 测试"""

    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = HypothesisReviewAgent()
        assert agent is not None

    @patch('app.agents.hypothesis_review_agent.qwen_structured_chat')
    def test_review_hypotheses(self, mock_qwen):
        """测试评审假设"""
        mock_qwen.return_value = {
            "reviews": [
                {
                    "hypothesis": "假设1",
                    "overall_score": 8.5,
                    "strengths": ["优点1"],
                    "weaknesses": ["缺点1"],
                    "recommendation": "推荐"
                }
            ],
            "top_pick": 0
        }
        
        agent = HypothesisReviewAgent()
        response = agent.review("研究问题", [
            {"statement": "假设1", "rationale": "理由1"}
        ])
        
        assert response is not None
        assert len(response.reviews) >= 1
        mock_qwen.assert_called()


@pytest.mark.agent
class TestReportGenerationAgent:
    """报告生成 Agent 测试"""

    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        agent = ReportGenerationAgent()
        assert agent is not None

    @patch('app.agents.report_generation_agent.qwen_structured_chat')
    def test_generate_report(self, mock_qwen):
        """测试生成报告"""
        mock_qwen.return_value = {
            "paper_title": "论文标题",
            "abstract": "摘要内容",
            "introduction": "引言",
            "related_work": "相关工作",
            "methodology": "方法论",
            "results": "结果",
            "discussion": "讨论",
            "conclusion": "结论",
            "references": ["参考文献1"]
        }
        
        agent = ReportGenerationAgent()
        response = agent.generate(
            "问题理解",
            [],
            [],
            "假设",
            "实验设计",
            "验证结果"
        )
        
        assert response is not None
        assert response.paper_title is not None
        assert response.abstract is not None
        mock_qwen.assert_called()
