"""图表数据分层抽取 — L1 规则 / L2 近似序列 / CSV 输出"""
from __future__ import annotations

import csv
import os
import re
from typing import Any, Dict, List, Optional


def extract_rule_series_from_caption(
    caption: str,
    series_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """从 caption 规则抽取近似数据点（低置信，需人工复核）。"""
    caption = caption or ""
    names = list(series_names or [])
    if not names:
        names = re.findall(
            r"(FedAvg|FedProx|SCAFFOLD|LocalOnly|Centralized|Ours|Baseline|[A-Z][a-z]+Net)",
            caption,
        )
    if not names:
        names = ["series_1"]

    rows: List[Dict[str, Any]] = []
    number_matches = re.findall(r"(\d+\.?\d*)\s*%?", caption)
    nums = [float(x) for x in number_matches[: len(names) * 2]] if number_matches else []

    for i, name in enumerate(names[:6]):
        val = nums[i] if i < len(nums) else None
        rows.append({
            "series": name,
            "value": val if val is not None else "",
            "unit": "approx_from_caption",
            "_provenance_extraction_method": "rule_series",
            "_confidence": 0.45,
        })
    return rows


def write_figure_series_csv(
    output_path: str,
    rows: List[Dict[str, Any]],
    figure_meta: Dict[str, Any],
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    has_xy = any(row.get("x") not in (None, "") or row.get("y") not in (None, "") for row in rows)
    fieldnames = ["figure_id", "figure_number", "series", "value", "unit",
                  "_provenance_extraction_method", "_confidence",
                  "_provenance_source_title", "_provenance_paper_id"]
    if has_xy:
        fieldnames = ["figure_id", "figure_number", "series", "x", "y", "value", "unit",
                      "_provenance_extraction_method", "_confidence",
                      "_provenance_source_title", "_provenance_paper_id"]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "figure_id": figure_meta.get("figure_id", ""),
                "figure_number": figure_meta.get("figure_number", ""),
                "series": row.get("series", ""),
                "x": row.get("x", ""),
                "y": row.get("y", ""),
                "value": row.get("value", ""),
                "unit": row.get("unit", ""),
                "_provenance_extraction_method": row.get(
                    "_provenance_extraction_method", figure_meta.get("extraction_method", "rule")
                ),
                "_confidence": row.get("_confidence", figure_meta.get("extraction_confidence", 0.4)),
                "_provenance_source_title": figure_meta.get("source_title", ""),
                "_provenance_paper_id": figure_meta.get("paper_id", ""),
            })
    return output_path
