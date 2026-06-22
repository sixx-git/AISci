"""JSON 列表/字典字段解析 — ORM Text 列与 API 共用"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def parse_json_list(raw: Any, default: Optional[List[Any]] = None) -> List[Any]:
    if default is None:
        default = []
    if raw is None:
        return list(default)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else list(default)
        except (json.JSONDecodeError, TypeError):
            return list(default)
    return list(default)


def parse_json_dict(raw: Any, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if default is None:
        default = {}
    if raw is None:
        return dict(default)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else dict(default)
        except (json.JSONDecodeError, TypeError):
            return dict(default)
    return dict(default)
