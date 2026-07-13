"""知识缺口 prompt 与传参测试。"""
from unittest.mock import patch

from app.agents.knowledge_gap_agent import KnowledgeGapAgent


@patch("app.agents.knowledge_gap_agent.qwen_structured_chat")
def test_knowledge_gap_prompt_includes_research_question(mock_chat):
    mock_chat.return_value = {
        "known_facts": [],
        "knowledge_gaps": [],
        "contradictions": [],
        "possible_connections": [],
        "research_opportunities": [],
    }
    agent = KnowledgeGapAgent()
    agent.analyze(
        facts=[{"fact_id": "fact_001", "content": "合成数据存在隐私风险"}],
        uncertain_points=["分布偏移尚不明确"],
        research_question="联邦康养场景下合成跌倒数据带来什么新挑战？",
        main_contradiction="稀缺样本需求 vs 生成失真",
        expected_output_summary="量化生成负面效应; 提出过滤算法",
    )
    prompt = mock_chat.call_args.kwargs.get("prompt") or mock_chat.call_args[1].get("prompt", "")
    assert "联邦康养" in prompt
    assert "主要矛盾" in prompt or "稀缺样本" in prompt
    assert "尚未解决的新挑战" in prompt or "缺口聚焦" in prompt
