"""报告正文净化测试。"""
from app.services.report_content_sanitizer import (
    sanitize_chapters,
    sanitize_report_result,
    strip_operational_bracket_sections,
)


def test_sanitize_removes_llm_agent_from_technical_details():
    chapters = sanitize_chapters(
        {
            "technical_details": (
                "采用 Qwen 大模型与多智能体 Pipeline 进行文献 RAG 检索。\n"
                "使用 DNA 折纸自组装与流式细胞术评估免疫逃逸。"
            ),
            "methods": "1. 文献事实抽取\n2. 假设生成与筛选\n3. 微流控实验",
        }
    )
    tech = chapters["technical_details"]
    assert "Qwen" not in tech
    assert "智能体" not in tech
    assert "DNA 折纸" in tech
    methods = chapters["methods"]
    assert "文献事实抽取" not in methods
    assert "微流控实验" in methods


def test_sanitize_report_result():
    result = sanitize_report_result(
        {
            "paper_abstract": "本研究结合千问大模型与智能体生成纳米机器人假设。",
            "chapters": {"technical_details": "向量检索 + FAISS 索引"},
            "markdown_content": "## 必要的技术手段\n\n使用 LLM 生成假设。",
        }
    )
    assert "千问" not in result["paper_abstract"]
    assert "向量检索" not in result["chapters"]["technical_details"]
    assert "LLM" not in result["markdown_content"]


def test_strip_operational_bracket_sections():
    raw = (
        "主要使用 NASA Exoplanet Archive。\n\n"
        "【推荐外部数据库/数据集】\n"
        "- Zenodo dataset [$pending_download$]: html snippet\n\n"
        "【多源数据查找与整合】\n"
        "DataSpec 场景=general；已合并 CSV：3813 行。\n"
        "数据发现完备性得分：83.3/100。\n\n"
        "科学数据来源包括 TESS 光变曲线。"
    )
    cleaned = strip_operational_bracket_sections(raw)
    assert "【" not in cleaned
    assert "DataSpec" not in cleaned
    assert "pending_download" not in cleaned
    assert "NASA Exoplanet Archive" in cleaned
    assert "TESS 光变曲线" in cleaned


def test_sanitize_results_removes_pipeline_notes():
    chapters = sanitize_chapters(
        {
            "results": {
                "simulated_results": [
                    "【整合数据集】data_finder 合并 CSV：3813 行；清洗 3813→3813 行。",
                ],
                "expected_results": [
                    "小样验证未执行；上列为已上传/合并数据的描述性统计。",
                    "预期通过 MCMC 获得 w 的后验约束。",
                ],
                "actual_results": [],
            }
        }
    )
    results = chapters["results"]
    assert results["simulated_results"] == []
    assert len(results["expected_results"]) == 1
    assert "MCMC" in results["expected_results"][0]
    assert "小样验证未执行" not in str(results)
