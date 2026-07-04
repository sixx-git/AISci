"""报告章节字段 — 与 latex_template/scientific_plan_template.tex 对齐。"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# 与 latex_template 一致的中文章节标题（人在回路 / 合规检查 / 前端展示共用）
REPORT_SECTION_FIELDS: List[Tuple[str, str]] = [
    ("paper_title", "论文标题"),
    ("paper_abstract", "摘要"),
    ("problem_statement", "待研究问题"),
    ("rationale", "解决思路"),
    ("technical_details", "必要的技术手段"),
    ("datasets", "数据集"),
    ("source", "历史数据"),
    ("target", "目标数据"),
    ("methods", "方法论"),
    ("experiments", "实验设计"),
    ("results", "实验结果"),
    ("references", "参考文献"),
]

REPORT_FIELD_KEYS = [k for k, _ in REPORT_SECTION_FIELDS] + ["markdown_content", "title"]

REPORT_SECTION_KEY_SET = {k for k, _ in REPORT_SECTION_FIELDS}

REPORT_SECTION_LABEL_MAP: Dict[str, str] = dict(REPORT_SECTION_FIELDS)


def report_orm_to_dict(report: Any) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for key in REPORT_FIELD_KEYS:
        val = getattr(report, key, None)
        data[key] = str(val) if val is not None else ""
    return data


def apply_report_dict(report: Any, data: Dict[str, Any]) -> None:
    for key in REPORT_FIELD_KEYS:
        if key in data and data[key] is not None:
            setattr(report, key, str(data[key]))


def normalize_section_keys(section_keys: List[str] | None) -> List[str]:
    if not section_keys:
        return []
    out: List[str] = []
    for raw in section_keys:
        key = (raw or "").strip()
        if key and key in REPORT_SECTION_KEY_SET and key not in out:
            out.append(key)
    return out
