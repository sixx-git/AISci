"""报告 12 章节字段 — 人在回路局部修订共用"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

REPORT_SECTION_FIELDS: List[Tuple[str, str]] = [
    ("paper_title", "1. Paper Title"),
    ("paper_abstract", "2. Paper Abstract"),
    ("problem_statement", "3. Problem Statement"),
    ("rationale", "4. Rationale"),
    ("technical_details", "5. Technical Details"),
    ("datasets", "6. Datasets"),
    ("source", "7. Source"),
    ("target", "8. Target"),
    ("methods", "9. Methods"),
    ("experiments", "10. Experiments"),
    ("results", "11. Results"),
    ("references", "12. References"),
]

REPORT_FIELD_KEYS = [k for k, _ in REPORT_SECTION_FIELDS] + ["markdown_content", "title"]

REPORT_SECTION_KEY_SET = {k for k, _ in REPORT_SECTION_FIELDS}


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
