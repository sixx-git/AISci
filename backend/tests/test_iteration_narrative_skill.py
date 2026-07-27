from app.skills.report.iteration_narrative_skill import (
    IterationNarrativeSkill,
    _format_decision_reason,
    _humanize_assessment,
)
from app.services.latex_export_service import escape_latex


def test_humanize_significant_issue():
    assert _humanize_assessment("significant_issue") == "需重大调整"
    assert "significant" not in _humanize_assessment("significant_issue")


def test_format_decision_reason_list_literal():
    raw = "['优先修复波长轴', '重新审查列分类']"
    out = _format_decision_reason(raw)
    assert "['" not in out
    assert "优先修复波长轴" in out
    assert "重新审查列分类" in out


def test_story_arc_keeps_full_plan_and_reason():
    plan = (
        "基于上轮反馈，重构波长轴提取逻辑（直接从2500系列列名解析波长值），"
        "重新分类数据列（区分泵浦功率参数列、光谱强度列与元数据），"
        "引入物理约束验证与辐射定标，改进空间相干性评估方法（使用自相关函数替代简单方差）。"
    )
    reason = (
        "['首先检查原始CSV文件的前几行和前几列，确认2500系列列名的真实物理含义"
        "（是波长nm值还是通道编号），必要时读取元数据文件或README', "
        "'重新审视数据矩阵的组织方式：4095行可能代表不同泵浦功率条件/时间步而非空间采样点，"
        "需根据元数据或实验日志确认行维度含义']"
    )
    narr = IterationNarrativeSkill.build_narrative(
        small_validation={
            "hypothesis": "通过超连续谱与无序超表面耦合实现类阳光非相干强激光。" * 3,
            "results": {
                "actual_results": {
                    "successful_iterations": [
                        {
                            "iteration_number": 2,
                            "status": "completed",
                            "plan_summary": plan,
                            "decision_reason": reason,
                            "overall_assessment": "significant_issue",
                        }
                    ]
                }
            },
        }
    )
    story = narr["story_arc"]
    assert "替代简单方差" in story
    assert "需根据元数据或实验日志确认行维度含义" in story
    assert "需重大调整" in story
    assert "significant_issue" not in story
    assert "['" not in story


def test_escape_latex_does_not_mathify_significant_issue():
    escaped = escape_latex("评估为「significant_issue」")
    assert "$significant" not in escaped
    assert "$" not in escaped or "$significant" not in escaped
    # 不得升成数学下标；允许正文转义 significant\_issue
    assert r"significant\_issue" in escaped or "significant issue" in escaped
