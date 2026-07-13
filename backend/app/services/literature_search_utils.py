"""文献检索通用工具（query 规范化等）。"""
from __future__ import annotations

import re
from typing import List, Set


def normalize_api_search_query(query: str) -> str:
    """将 LLM 布尔检索式转为 API 友好的空格关键词。"""
    q = (query or "").strip()
    if not q:
        return ""
    phrases = re.findall(r'"([^"]+)"', q)
    q = re.sub(r"\b(AND|OR|NOT)\b", " ", q, flags=re.I)
    q = re.sub(r'["\(\)]', " ", q)
    tokens: List[str] = []
    for p in phrases:
        p = p.strip()
        if len(p) >= 2:
            tokens.append(p)
    for t in re.split(r"[\s,，；;、/|]+", q):
        t = t.strip()
        if len(t) >= 2 and t.lower() not in ("and", "or", "not"):
            tokens.append(t)
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return " ".join(out[:12])[:240]


def normalize_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", t)
    return " ".join(t.split())


def titles_match(a: str, b: str, *, min_ratio: float = 0.55) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(len(ta), len(tb))
    return overlap >= min_ratio
