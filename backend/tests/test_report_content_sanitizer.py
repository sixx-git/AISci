"""报告正文净化测试。"""
from app.services.report_content_sanitizer import sanitize_chapters, sanitize_report_result


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
