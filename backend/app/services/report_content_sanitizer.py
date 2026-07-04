"""
报告正文净化：移除与具体科学问题无关的平台/大模型/智能体描述。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 整行删除：明显属于系统实现而非科学内容
_DROP_LINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"qwen|千问|通义|百炼|dashscope",
        r"大语言模型|大模型|llm\b|gpt-?[34]",
        r"智能体|multi-?agent|agent\s*pipeline",
        r"\bRAG\b|向量检索|faiss|embedding",
        r"AI[\s-]?Scientist|ai scientist",
        r"多智能体|pipeline\s*阶段|prompt\s*版本",
        r"人在回路|human[\s-]?in[\s-]?the[\s-]?loop",
        r"文献事实抽取|假设生成与筛选|假设生成与评审",
        r"api\s*调用|结构化输出|token",
    ]
]

# 短语替换：保留句子但去掉平台措辞
_PHRASE_REPLACEMENTS = [
    (re.compile(r"LLM\s*生成的?", re.I), ""),
    (re.compile(r"大模型生成的?", re.I), ""),
    (re.compile(r"由\s*智能体\s*", re.I), "通过"),
    (re.compile(r"智能体\s*", re.I), ""),
    (re.compile(r"多智能体\s*Pipeline", re.I), "研究流程"),
    (re.compile(r"AI[\s-]?Scientist\s*(平台|系统|Pipeline)?", re.I), ""),
    (re.compile(r"沙箱实测", re.I), "初步实验验证"),
    (re.compile(r"沙箱执行", re.I), "实验执行"),
    (re.compile(r"sandbox\s*execution", re.I), "pilot experiment"),
    (re.compile(r"产物目录\s*[:：]\s*`[^`]+`", re.I), ""),
    (re.compile(r"运行\s*ID\s*[:：|｜]\s*\S+", re.I), ""),
]

_SCIENCE_FACING_CHAPTER_KEYS = (
    "problem_statement",
    "rationale",
    "technical_details",
    "datasets",
    "source",
    "target",
    "methods",
    "experiments",
    "results",
)


def _clean_line(line: str, *, preserve_platform_terms: bool = False) -> Optional[str]:
    stripped = line.strip()
    if not stripped:
        return ""
    for pat in _DROP_LINE_PATTERNS:
        if preserve_platform_terms and "qwen" in pat.pattern.lower():
            continue
        if pat.search(stripped):
            return None
    text = line
    for pat, repl in _PHRASE_REPLACEMENTS:
        text = pat.sub(repl, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;，。；])", r"\1", text)
    return text.rstrip()


def sanitize_text(text: Any, *, preserve_platform_terms: bool = False) -> str:
    """净化单段文本或保留结构的列表项。"""
    if text is None:
        return ""
    if isinstance(text, list):
        cleaned_items: List[str] = []
        for item in text:
            part = sanitize_text(item, preserve_platform_terms=preserve_platform_terms)
            if part.strip():
                cleaned_items.append(part.strip())
        return "\n".join(f"- {item}" if not item.startswith("-") else item for item in cleaned_items)
    if isinstance(text, dict):
        parts = []
        for key, val in text.items():
            if val in (None, "", [], {}):
                continue
            val_str = sanitize_text(val, preserve_platform_terms=preserve_platform_terms)
            if val_str.strip():
                parts.append(f"{key}: {val_str}")
        return "\n".join(parts)

    raw = str(text).replace("\\n", "\n")
    out_lines: List[str] = []
    for line in raw.splitlines():
        cleaned = _clean_line(line, preserve_platform_terms=preserve_platform_terms)
        if cleaned is None:
            continue
        out_lines.append(cleaned)
    return "\n".join(out_lines).strip()


def sanitize_chapters(chapters: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(chapters, dict):
        return chapters
    cleaned = dict(chapters)
    for key in _SCIENCE_FACING_CHAPTER_KEYS:
        if key not in cleaned:
            continue
        val = cleaned[key]
        if isinstance(val, dict):
            cleaned[key] = {k: sanitize_text(v) for k, v in val.items()}
        elif key == "technical_details":
            cleaned[key] = sanitize_text(val, preserve_platform_terms=True)
        else:
            cleaned[key] = sanitize_text(val)
    return cleaned


def sanitize_markdown_document(markdown: str) -> str:
    if not markdown:
        return markdown

    skip_sections = {"运行摘要", "参考文献提醒", "图表数据提醒", "Figures"}
    out: List[str] = []
    in_skip = False

    for line in markdown.splitlines():
        heading = re.match(r"^#{1,3}\s+(.+)", line.strip())
        if heading:
            title = heading.group(1).strip()
            in_skip = any(title.startswith(s) for s in skip_sections)
        if in_skip:
            out.append(line)
            continue
        cleaned = _clean_line(line)
        if cleaned is None:
            continue
        out.append(cleaned)

    return "\n".join(out).strip()


def sanitize_report_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """净化结构化报告，供 Markdown 与 LaTeX 导出使用。"""
    out = dict(result)
    chapters = out.get("chapters")
    if isinstance(chapters, dict):
        out["chapters"] = sanitize_chapters(chapters)
        # 有结构化 chapters 时不再保留 Markdown 正文，仅 LaTeX PDF 导出
        out["markdown_content"] = ""
    if out.get("paper_abstract"):
        out["paper_abstract"] = sanitize_text(out["paper_abstract"])
    elif out.get("markdown_content"):
        out["markdown_content"] = sanitize_markdown_document(out["markdown_content"])
    return out
