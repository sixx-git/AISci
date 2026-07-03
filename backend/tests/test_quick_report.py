"""一键报告服务测试"""
from app.core.pipeline_modes import resolve_run_options
from app.services.quick_report_service import build_research_question


def test_build_research_question():
    q = build_research_question("肺癌预测", "TCGA 表达矩阵 + 临床表型")
    assert "肺癌预测" in q
    assert "TCGA" in q


def test_quick_report_run_options():
    opts = resolve_run_options({"enable_quick_report": True})
    assert opts["pipeline_mode"] == "discovery"
    assert opts["enable_hitl_gate"] is False
    assert opts["enable_quick_report"] is True
