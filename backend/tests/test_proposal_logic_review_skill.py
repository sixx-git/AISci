"""开题报告科学逻辑 Skill 与问题理解扩展字段测试"""
import asyncio

from app.agents.problem_understanding_agent import (
    ProblemUnderstandingResponse,
    ResearchObject,
    build_scientific_logic_constraints,
    resolve_research_question_from_pu,
)
from app.skills.report.proposal_logic_review_skill import ProposalLogicReviewSkill


def test_build_scientific_logic_constraints():
    pu = {
        "main_contradiction": "样本不足与泛化需求矛盾",
        "research_object": {"internal": "模型", "external": "数据", "boundary": "小样本"},
        "expected_output": ["提升 F1"],
    }
    lines = build_scientific_logic_constraints(pu)
    assert any("主要矛盾" in line for line in lines)
    assert any("研究对象拆解" in line for line in lines)


def test_resolve_research_question_from_pu():
    assert resolve_research_question_from_pu({"problem_statement": "具体问题"}) == "具体问题"
    assert resolve_research_question_from_pu({}, fallback="默认") == "默认"


def test_problem_understanding_response_accepts_scientific_fields():
    resp = ProblemUnderstandingResponse(
        problem_statement="问题",
        research_domain="AI",
        keywords=["k"],
        scope_boundary="边界",
        constraints=[],
        expected_output=["输出"],
        main_contradiction="主要矛盾",
        research_object=ResearchObject(internal="内", external="外", boundary="界"),
    )
    assert resp.main_contradiction == "主要矛盾"
    assert resp.research_object.boundary == "界"


def test_proposal_logic_review_rule_checks_pass():
    skill = ProposalLogicReviewSkill()
    pu = {
        "main_contradiction": "理论预测与实验观测不一致",
        "research_object": {"internal": "材料结构", "external": "湿度环境", "boundary": "实验室条件"},
        "scope_boundary": "限定实验室尺度",
    }
    kg = {"knowledge_gaps": [{"description": "湿环境下机制尚未阐明"}]}
    report = {
        "chapters": {
            "problem_statement": "现有模型无法解释湿度导致的反直觉滑移矛盾。",
            "rationale": "已知事实表明摩擦系数随湿度变化，但知识空白是微观机制尚未研究，因此提出新假设。",
            "methods": "设计对照实验，测量摩擦系数与微观形变，使用 baseline 对比验证假设。",
            "experiments": "设置三组湿度条件，指标为摩擦系数与重现率。",
        }
    }
    result = asyncio.run(skill.run(
        {"problem_understanding": pu, "knowledge_gaps": kg, "report_data": report},
        {},
    ))
    data = result.data
    assert data["has_main_contradiction"] is True
    assert data["has_object_decomposition"] is True
    assert data["logic_score"] >= 5.0


def test_proposal_logic_review_detects_missing_contradiction():
    skill = ProposalLogicReviewSkill()
    report = {"chapters": {"problem_statement": "本研究很重要。", "rationale": "因此做研究。", "methods": "分析。"}}
    result = asyncio.run(skill.run(
        {"problem_understanding": {}, "knowledge_gaps": {}, "report_data": report},
        {},
    ))
    assert result.data["has_main_contradiction"] is False
    assert result.data["issues"]
