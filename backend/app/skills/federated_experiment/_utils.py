"""联邦实验 Skill 共享工具"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


def normalize_col(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_")


def match_fields(columns: Iterable[str], candidates: List[str]) -> List[str]:
    norm_cols = {normalize_col(c): c for c in columns}
    matched: List[str] = []
    for cand in candidates:
        nc = normalize_col(cand)
        if nc in norm_cols:
            matched.append(norm_cols[nc])
    return matched


def unique_preserve(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        key = normalize_col(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
