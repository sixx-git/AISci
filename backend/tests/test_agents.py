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

    @patch('app.agents.literature_mining_agent.LiteratureMiningAgent._run_skills_sync', return_value={})
    @patch('app.agents.literature_mining_agent.LiteratureMiningAgent._rerank_chunks')
    @patch('app.agents.literature_mining_agent.search_vector_store')
    @patch('app.agents.literature_mining_agent.get_vector_store')
    @patch('app.agents.literature_mining_agent.qwen_structured_chat')
    def test_mine_literature(self, mock_qwen, mock_vs_factory, mock_search, mock_rerank, _mock_skills):
        """测试文献挖掘（现行 facts / citation_map 契约）"""
        from app.services.vector_store import SearchResult

        mock_vs = MagicMock()
        mock_vs.has_index.return_value = True
        mock_vs_factory.return_value = mock_vs
        sr = SearchResult(
            chunk_id="c1",
            document_id="d1",
            content="城市绿化可降低地表温度。",
            page_number=1,
            source_title="研究1",
            similarity_score=0.9,
        )
        mock_search.return_value = [sr]
        mock_rerank.return_value = ([sr], {})
        mock_qwen.return_value = {
            "facts": [
                {
                    "fact_id": "fact_001",
                    "content": "发现1",
                    "source_chunk_id": "c1",
                    "document_id": "d1",
                    "source_paper_title": "研究1",
                    "quote_text": "城市绿化可降低地表温度。",
                },
                {
                    "fact_id": "fact_002",
                    "content": "发现2",
                    "source_chunk_id": "c1",
                    "document_id": "d1",
                    "source_paper_title": "研究1",
                },
            ],
            "evidence": [],
            "source_papers": ["研究1"],
            "citation_map": [
                {
                    "document_id": "d1",
                    "paper_title": "研究1",
                    "fact_ids": ["fact_001", "fact_002"],
                    "chunk_ids": ["c1"],
                }
            ],
            "uncertain_points": [],
        }

        agent = LiteratureMiningAgent()
        response = agent.mine("test_project", "研究问题")

        assert response is not None
        assert hasattr(response, "facts")
        assert len(response.facts) >= 2
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
                    "hypothesis": "假设陈述1",
                    "rationale": "理由1",
                    "novelty": "创新点1",
                    "testability": "可测1",
                    "required_data": "数据1",
                    "possible_method": "方法1",
                    "risk": "风险1",
                    "supporting_fact_ids": [],
                    "evidence_level": "low",
                },
                {
                    "hypothesis": "假设陈述2",
                    "rationale": "理由2",
                    "novelty": "创新点2",
                    "testability": "可测2",
                    "required_data": "数据2",
                    "possible_method": "方法2",
                    "risk": "风险2",
                    "supporting_fact_ids": [],
                    "evidence_level": "low",
                },
            ],
            "summary": "测试摘要",
        }

        agent = HypothesisGenerationAgent()
        response = agent.generate("研究问题", [], [], constraints=[])

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
                    "hypothesis_index": 0,
                    "hypothesis": "假设1",
                    "overall_score": 8.5,
                    "scores": {
                        "scientific_value": {"score": 8, "reason": "ok"},
                        "novelty": {"score": 8, "reason": "ok"},
                        "testability": {"score": 9, "reason": "ok"},
                        "data_availability": {"score": 8, "reason": "ok"},
                        "cost_risk": {"score": 8, "reason": "ok"},
                    },
                    "suggestions": "建议1",
                    "strengths": ["优点1"],
                    "weaknesses": ["缺点1"],
                }
            ],
            "summary": "总体评价",
        }

        agent = HypothesisReviewAgent()
        response = agent.review(
            [{"hypothesis": "假设1", "rationale": "理由1"}],
            research_question="研究问题",
        )

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
            "title": "科学假设与研究计划",
            "paper_title": "论文标题",
            "paper_abstract": "摘要内容",
            "markdown_content": "",
            "chapters": {
                "problem_statement": "问题陈述",
                "rationale": "原理依据",
                "technical_details": "技术细节",
                "datasets": "数据集",
                "source": "源数据",
                "target": "目标",
                "methods": "方法",
                "experiments": "实验",
                "results": "结果",
                "references": ["参考文献1"],
            },
        }

        agent = ReportGenerationAgent()
        response = agent.generate_report(
            project_info={"title": "测试项目"},
            problem_understanding={"problem_statement": "问题理解"},
            literature_facts=[],
            citation_map=[],
            knowledge_gaps={},
            all_hypotheses=[{"hypothesis": "假设"}],
            final_hypothesis={"hypothesis": "假设"},
            experiment_design={"methods": "实验设计"},
            small_validation={"results": {"actual_results": {}}},
        )

        assert response is not None
        assert response.get("paper_title") is not None
        assert (response.get("paper_abstract") or response.get("chapters", {}).get("problem_statement"))
        mock_qwen.assert_called()
