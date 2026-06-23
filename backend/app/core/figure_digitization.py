"""图表 L3/L4 数值数字化 — JSON schema 校验与点列转换"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

FIGURE_SERIES_SCHEMA_V2: Dict[str, Any] = {
    "series": [
        {
            "name": "FedAvg",
            "points": [{"x": 0, "y": 0.72}, {"x": 10, "y": 0.85}],
        }
    ],
    "x_axis_label": "Communication rounds",
    "y_axis_label": "Accuracy",
    "chart_type": "line",
    "warnings": [],
}

MIN_L4_POINTS = 10
L4_CONFIDENCE_THRESHOLD = 0.75


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def validate_digitized_series(payload: Dict[str, Any]) -> Tuple[List[str], float, int]:
    """校验 VLM 结构化输出，返回 (auto_checks, confidence, points_count)。"""
    checks: List[str] = []
    confidence = 0.55
    series_list = payload.get("series") if isinstance(payload.get("series"), list) else []
    if not series_list:
        return checks, 0.45, 0

    checks.append("json_schema_ok")
    total_points = 0
    valid_series = 0

    for item in series_list:
        if not isinstance(item, dict):
            continue
        points = item.get("points") if isinstance(item.get("points"), list) else []
        parsed: List[Tuple[float, float]] = []
        for pt in points:
            if not isinstance(pt, dict):
                continue
            x = _to_float(pt.get("x"))
            y = _to_float(pt.get("y"))
            if x is not None and y is not None:
                parsed.append((x, y))
        if not parsed:
            continue
        valid_series += 1
        total_points += len(parsed)
        if len(parsed) >= 2:
            xs = [p[0] for p in parsed]
            if xs == sorted(xs) or xs == sorted(xs, reverse=True):
                checks.append("monotonic_x")
                break

    if valid_series >= 1:
        checks.append("series_present")
        confidence += 0.08
    if total_points >= MIN_L4_POINTS:
        checks.append("min_points_ok")
        confidence += 0.12
    elif total_points >= 4:
        checks.append("sparse_points")
        confidence += 0.05

    ys: List[float] = []
    for item in series_list:
        if not isinstance(item, dict):
            continue
        for pt in item.get("points") or []:
            if isinstance(pt, dict):
                y = _to_float(pt.get("y"))
                if y is not None:
                    ys.append(y)
    if ys and all(-1e6 <= y <= 1e6 for y in ys):
        checks.append("value_range_ok")
        confidence += 0.05

    confidence = round(min(0.92, confidence), 4)
    return list(dict.fromkeys(checks)), confidence, total_points


def series_json_to_rows(
    payload: Dict[str, Any],
    *,
    extraction_method: str = "vlm_digitize",
    base_confidence: float = 0.75,
) -> List[Dict[str, Any]]:
    """将结构化 series JSON 转为 CSV 行（含 x/y）。"""
    rows: List[Dict[str, Any]] = []
    for item in payload.get("series") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "series")[:80]
        for pt in item.get("points") or []:
            if not isinstance(pt, dict):
                continue
            x = _to_float(pt.get("x"))
            y = _to_float(pt.get("y"))
            if x is None and y is None:
                continue
            rows.append({
                "series": name,
                "x": x if x is not None else "",
                "y": y if y is not None else "",
                "value": y if y is not None else "",
                "unit": "digitized",
                "_provenance_extraction_method": extraction_method,
                "_confidence": base_confidence,
            })
    return rows


def infer_tier_from_digitization(
    *,
    method: str,
    confidence: float,
    points_count: int,
    checks: List[str],
) -> str:
    if method == "vlm_digitize" and points_count >= MIN_L4_POINTS and confidence >= L4_CONFIDENCE_THRESHOLD:
        if "min_points_ok" in checks and "json_schema_ok" in checks:
            return "L4_digitize"
    if method in ("vlm_digitize", "vlm_structured"):
        return "L3_vlm"
    if method == "rule_series":
        return "L2_rule_series"
    return "L1_metadata"


def sanitize_vlm_series_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """规范化 VLM 返回，兼容嵌套或缺字段。"""
    if not isinstance(raw, dict):
        return {"series": [], "warnings": ["invalid_payload"]}
    out = dict(raw)
    if "series" not in out and isinstance(out.get("data"), dict):
        out = out["data"]
    series = out.get("series")
    if not isinstance(series, list):
        # 尝试从 key_trends 降级（旧 VLM 格式）
        trends = out.get("key_trends") or out.get("detected_elements") or []
        if trends:
            out["series"] = [{"name": str(t)[:60], "points": []} for t in trends[:4]]
        else:
            out["series"] = []
    out.setdefault("warnings", [])
    return out
