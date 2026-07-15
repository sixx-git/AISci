"""
评分项可观测性（OCR — Observable Checklist Rubric）工具。

用于生成阶段校验/操作化，以及打分阶段按 judgment_mode 判分。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# 问句中含以下结构之一，视为已有「可观察锚点」
OPERATIONAL_MARKERS: tuple[str, ...] = (
    r"\bi\.e\.[, ]",
    r"\bthat is[, ]",
    r"\bspecifically\b",
    r"\bincluding\b",
    r"\bnamely\b",
    r"\bdefined as\b",
    r"\bimplemented by\b",
    r"\bcharacterized by\b",
    r"\bat least (?:two|three|\d+) of the following\b",
    r"\ball (?:three|two|\d+) of the following\b",
    r"\bthe following (?:three|two|\d+) (?:elements|points|conditions)\b",
    r", that [a-z]",  # "... explain X, that Y..."
    r"\bbecause [a-z]",
    r"\bleads to\b",
    r"\bresults in\b",
    r"\bconsists of\b",
)

EXPLAIN_DEFINE_RE = re.compile(
    r"\b(explicitly\s+)?(define|defines|defined|explain|explains|explained)\b",
    re.I,
)

VAGUE_DEGREE_RE = re.compile(
    r"\b(adequately|sufficiently|comprehensively|thoroughly|in depth|in-depth|"
    r"fully|properly|clearly enough|well enough)\b",
    re.I,
)

# 不可独立判定的抽象指代
ABSTRACT_POINTER_RE = re.compile(
    r"\b(the mechanism|the key factor|the primary metric|the main challenge|"
    r"relevant concepts?|appropriate (?:method|approach|metric)s?|"
    r"the underlying (?:reason|cause|mechanism))\b",
    re.I,
)


def has_operational_clause(question: str) -> bool:
    q = (question or "").lower()
    return any(re.search(p, q) for p in OPERATIONAL_MARKERS)


def has_explain_or_define(question: str) -> bool:
    return bool(EXPLAIN_DEFINE_RE.search(question or ""))


def is_naked_explain_define(question: str, required_elements: Optional[List[str]] = None) -> bool:
    """explain/define 且无 required_elements 且无 operational 从句。"""
    if required_elements:
        return False
    if not has_explain_or_define(question):
        return False
    return not has_operational_clause(question)


def extract_elements_from_question(question: str) -> List[str]:
    """从 i.e. / that 从句等规则提取可观察要素（无需 LLM）。"""
    q = (question or "").strip()
    elements: List[str] = []

    m = re.search(r"\bi\.e\.[, ]+\s*(.+?)(?:\?|$)", q, re.I | re.S)
    if m:
        elements.append(m.group(1).strip().rstrip("?"))

    m = re.search(
        r"\b(?:defined|explained|implemented|characterized) as\s+(.+?)(?:\?|$)",
        q,
        re.I | re.S,
    )
    if m:
        elements.append(m.group(1).strip().rstrip("?"))

    m = re.search(
        r"\b(?:all|at least)\s+(?:three|two|\d+)\s+of the following[:\s]+(.+?)(?:\?|$)",
        q,
        re.I | re.S,
    )
    if m:
        block = m.group(1)
        for part in re.split(r"[;\n]|(?:\(\s*[A-C]\s*\))", block):
            part = re.sub(r"^\s*[A-C]\)\s*", "", part.strip())
            if len(part) > 15:
                elements.append(part.rstrip("?."))

    return [e for e in elements if e]


def infer_judgment_mode(
    question: str,
    dimension_id: str,
    required_elements: Optional[List[str]] = None,
) -> str:
    elems = required_elements or []
    if len(elems) >= 2:
        return "checklist"
    if dimension_id == "report_synthesis":
        return "structure"
    if has_operational_clause(question) and has_explain_or_define(question):
        return "binary"
    if re.search(r"\b(evaluate whether|state that|identify that|cite|distinguish)\b", question, re.I):
        return "binary"
    if elems:
        return "checklist"
    return "binary"


def default_checklist_thresholds(num_elements: int) -> Tuple[int, int]:
    """返回 (min_elements_full, min_elements_half)。"""
    if num_elements >= 3:
        return 3, 2
    if num_elements == 2:
        return 2, 1
    if num_elements == 1:
        return 1, 1
    return 1, 1


def enrich_item_observability(item: Dict[str, Any], dimension_id: str) -> Dict[str, Any]:
    """补全 judgment_mode / required_elements / 阈值字段。"""
    q = item.get("question", "")
    elems = item.get("required_elements") or []
    if isinstance(elems, str):
        elems = [elems]
    elems = [str(e).strip() for e in elems if str(e).strip()]

    if not elems:
        elems = extract_elements_from_question(q)

    mode = item.get("judgment_mode") or infer_judgment_mode(q, dimension_id, elems)
    min_full, min_half = item.get("min_elements_full"), item.get("min_elements_half")
    if min_full is None or min_half is None:
        mf, mh = default_checklist_thresholds(len(elems))
        min_full = min_full if min_full is not None else mf
        min_half = min_half if min_half is not None else mh

    return {
        **item,
        "required_elements": elems,
        "judgment_mode": mode,
        "min_elements_full": int(min_full),
        "min_elements_half": int(min_half),
    }


def item_passes_observability(item: Dict[str, Any], dimension_id: str) -> bool:
    """生成阶段最终过滤：是否保留该评分项。"""
    q = item.get("question", "")
    elems = item.get("required_elements") or []

    if VAGUE_DEGREE_RE.search(q):
        return False
    if dimension_id != "report_synthesis" and ABSTRACT_POINTER_RE.search(q):
        if not elems and not has_operational_clause(q):
            return False
    if dimension_id != "report_synthesis" and is_naked_explain_define(q, elems):
        return False
    if dimension_id != "report_synthesis":
        if has_explain_or_define(q) and not elems and not has_operational_clause(q):
            return False
    return True


def score_from_checklist(
    matched_count: int,
    weight: int,
    min_full: int,
    min_half: int,
) -> float:
    if matched_count >= min_full:
        return float(weight)
    if matched_count >= min_half:
        return float(weight) / 2.0
    return 0.0


def format_elements_for_prompt(elements: List[str]) -> str:
    if not elements:
        return "none (evaluate the single verifiable proposition in the question)"
    return "\n".join(f"  - ({chr(65 + i)}) {el}" for i, el in enumerate(elements))
