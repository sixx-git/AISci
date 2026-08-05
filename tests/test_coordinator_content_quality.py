"""
验证脚本：测试 CoordinatorAgent 的内容质量检查和 LLM 兜底分析
"""
import sys
import os
import json

# 从项目根目录执行时，把 backend 加入 path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, ".."))
_backend_dir = os.path.join(_project_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.agents.coordinator_agent import CoordinatorAgent


def test_check_report_content_quality():
    """测试 check_report_content_quality 方法"""
    print("=" * 60)
    print("测试 1: check_report_content_quality - 正常内容")
    chapters_normal = {
        "problem_statement": "这是一个正常的研究问题描述。它包含完整的内容，没有乱码或截断。",
        "rationale": "这是正常的 rationale 内容。包含了完整的句子，以句号结束。",
        "technical_details": "技术细节部分。所有内容都是正常的，没有异常字符。",
        "methods": "方法部分。内容完整，标点符号使用正确。",
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_normal)
    assert not result["has_issues"], f"正常内容不应有质量问题: {result}"
    print(f"  ✅ 通过: has_issues={result['has_issues']}, detail={result['detail']}")

    print("\n测试 2: check_report_content_quality - 乱码检测")
    chapters_garbled = {
        "problem_statement": "正常内容。",
        "technical_details": f"这里出现乱码字符{chr(0xFFFD)}和{chr(0xFFFE)}，应该被检测到。",
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_garbled)
    assert result["has_issues"], f"乱码内容应检测到问题: {result}"
    garbled = [i for i in result["issues"] if i["type"] == "garbled"]
    assert len(garbled) > 0, f"应检测到乱码问题: {result['issues']}"
    print(f"  ✅ 通过: 检测到 {len(garbled)} 处乱码")

    print("\n测试 3: check_report_content_quality - 截断检测")
    chapters_truncated = {
        "problem_statement": "正常内容。",
        "rationale": "这是一个被截断的章节内容。它很长但没有以句号结束" + "x" * 100,
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_truncated)
    assert result["has_issues"], f"截断内容应检测到问题: {result}"
    truncated = [i for i in result["issues"] if i["type"] == "truncated"]
    assert len(truncated) > 0, f"应检测到截断问题: {result['issues']}"
    print(f"  ✅ 通过: 检测到 {len(truncated)} 处截断")

    print("\n测试 4: check_report_content_quality - 标点重复检测")
    chapters_punct = {
        "problem_statement": "正常内容。",
        "datasets": "这里标点符号重复了。。。太多次了！！！还有，，逗号重复。",
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_punct)
    assert result["has_issues"], f"标点重复应检测到问题: {result}"
    repeated = [i for i in result["issues"] if i["type"] == "repeated_punctuation"]
    assert len(repeated) > 0, f"应检测到标点重复问题: {result['issues']}"
    print(f"  ✅ 通过: 检测到 {len(repeated)} 处标点重复")

    print("\n测试 5: check_report_content_quality - 混合问题")
    chapters_mixed = {
        "problem_statement": "正常内容。",
        "rationale": "被截断的 rationale 章节。" + "y" * 100,
        "technical_details": f"乱码{chr(0xFFFD)}内容。",
        "datasets": "标点重复。。。",
        "methods": "正常内容，没有问题。",
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_mixed)
    assert result["has_issues"], f"混合问题应检测到问题: {result}"
    assert result["issue_count"] >= 3, f"应检测到至少 3 个问题: {result}"
    types = set(i["type"] for i in result["issues"])
    print(f"  ✅ 通过: 检测到 {result['issue_count']} 个问题, 类型={types}")

    print("\n" + "=" * 60)
    print("测试 6: check_report_content_quality - LaTeX 转义残留检测")
    chapters_latex = {
        "problem_statement": "正常内容。",
        "rationale": "这里包含LaTeX转义残留\\_underscore和\\{brace\\}还有\\%percent。",
        "technical_details": "连续反斜杠\\\\和美元符\\$以及井号\\#。",
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_latex)
    assert result["has_issues"], f"LaTeX 转义残留应检测到问题: {result}"
    latex_issues = [i for i in result["issues"] if i["type"] == "latex_escape"]
    assert len(latex_issues) > 0, f"应检测到 LaTeX 转义问题: {result['issues']}"
    print(f"  ✅ 通过: 检测到 {len(latex_issues)} 处 LaTeX 转义残留: {[i['detail'] for i in latex_issues]}")

    print("\n" + "=" * 60)
    print("测试 7: check_report_content_quality - 空内容/非字符串")
    chapters_empty = {
        "empty_chapter": "",
        "none_chapter": None,
        "list_chapter": ["a", "b"],
    }
    result = CoordinatorAgent.check_report_content_quality(chapters_empty)
    # 空内容应该跳过，不对 list 类型报错
    print(f"  ✅ 通过: 空内容无异常 (has_issues={result['has_issues']})")


def test_build_error_snapshot_with_content_quality():
    """测试 build_error_snapshot 在 report_generation 阶段是否包含 content_quality"""
    print("\n" + "=" * 60)
    print("测试 9: build_error_snapshot - report_generation 阶段")
    coordinator = CoordinatorAgent()

    # 模拟有问题的报告结果
    result = {
        "quality_score": 85,
        "critical_issues": [],
        "missing_sections": [],
        "has_references": True,
        "refs_verified": 5,
        "chapters": {
            "problem_statement": "正常内容。",
            "rationale": f"乱码{chr(0xFFFD)}内容。",
            "datasets": "标点重复。。。",
        },
    }
    snapshot = coordinator.build_error_snapshot("report_generation", result)
    assert "content_quality" in snapshot, f"snapshot 应包含 content_quality: {snapshot.keys()}"
    cq = snapshot["content_quality"]
    assert cq["has_issues"], f"应有内容质量问题: {cq}"
    print(f"  ✅ 通过: content_quality 已注入 snapshot, has_issues={cq['has_issues']}, "
          f"issue_count={cq['issue_count']}")


def test_decide_remediation_triggers_auto_fix():
    """测试 decide_remediation 是否能正确触发 auto_fix_report"""
    print("\n" + "=" * 60)
    print("测试 10: decide_remediation - rg_content_quality 规则触发")
    coordinator = CoordinatorAgent()

    snapshot = {
        "quality_score": 85,
        "critical_issues": [],
        "missing_sections": [],
        "has_references": True,
        "refs_verified": 5,
        "content_quality": {
            "has_issues": True,
            "issue_count": 2,
            "issues": [
                {"chapter": "rationale", "type": "garbled", "detail": "发现 1 处乱码字符"},
                {"chapter": "datasets", "type": "repeated_punctuation", "detail": "发现 1 处句号重复"},
            ],
            "detail": "发现 2 个内容质量问题",
        },
    }
    decision = coordinator.decide_remediation("report_generation", snapshot)
    assert decision["source"] == "predefined", f"应为 predefined 规则匹配: {decision['source']}"
    assert decision["pattern_id"] == "rg_content_quality", f"应匹配 rg_content_quality 规则: {decision['pattern_id']}"
    assert decision["remediation"] == "auto_fix_report", f"应为 auto_fix_report: {decision['remediation']}"
    assert decision["action"]["type"] == "auto", f"action type 应为 auto: {decision['action']}"
    print(f"  ✅ 通过: 触发 pattern_id={decision['pattern_id']}, remediation={decision['remediation']}")


def test_has_anomaly():
    """测试 _has_anomaly 方法"""
    print("\n" + "=" * 60)
    print("测试 11: _has_anomaly - 异常检测")
    coordinator = CoordinatorAgent()

    # report_generation 异常检测：quality < 60 且无 critical_issues
    snapshot_low_quality = {
        "quality_score": 45,
        "critical_issues": [],
        "missing_sections": [],
        "has_references": True,
        "refs_verified": 0,
    }
    # 先匹配规则，rg_low_quality 的 condition 是 quality_score < 60
    # 所以会先被 rg_low_quality 匹配，不会走到 anomaly 检测
    # 需要 quality < 60 但 rules 的 condition 不匹配的情况
    # 实际上 rg_low_quality 的条件就是 quality_score < 60，所以一定会匹配
    # 这个测试验证 anomaly 检测逻辑本身
    anomaly = coordinator._has_anomaly("report_generation", snapshot_low_quality)
    print(f"  ℹ️  quality=45 时 _has_anomaly={anomaly}（会被 rg_low_quality 规则先匹配）")

    # 正常质量分，无异常
    snapshot_normal = {
        "quality_score": 85,
        "critical_issues": [],
    }
    anomaly = coordinator._has_anomaly("report_generation", snapshot_normal)
    assert not anomaly, f"正常质量分不应有异常: {anomaly}"
    print(f"  ✅ 通过: quality=85 时 _has_anomaly={anomaly}")


if __name__ == "__main__":
    test_check_report_content_quality()
    test_build_error_snapshot_with_content_quality()
    test_decide_remediation_triggers_auto_fix()
    test_has_anomaly()
    print("\n" + "=" * 60)
    print("🎉 所有测试通过!")