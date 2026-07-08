"""数据集规模分级 — 大文件上传、探查、沙箱策略。"""
from __future__ import annotations

from typing import Any, Dict, Optional

# 字节阈值（可被 Settings 覆盖）
TIER0_MAX_BYTES = 50 * 1024 * 1024          # ≤50MB：全表 pandas 可接受
TIER1_MAX_BYTES = 500 * 1024 * 1024         # ≤500MB：DuckDB 探查 + 采样沙箱
TIER2_MAX_BYTES = 2 * 1024 * 1024 * 1024    # ≤2GB：采样沙箱 + 分区策略


def resolve_analysis_tier(file_size_bytes: Optional[int]) -> str:
    """返回 T0 / T1 / T2 / T3。"""
    size = int(file_size_bytes or 0)
    if size <= 0:
        return "T0"
    if size <= TIER0_MAX_BYTES:
        return "T0"
    if size <= TIER1_MAX_BYTES:
        return "T1"
    if size <= TIER2_MAX_BYTES:
        return "T2"
    return "T3"


def tier_sandbox_timeout_sec(tier: str) -> int:
    return {"T0": 120, "T1": 300, "T2": 600, "T3": 900}.get(tier, 120)


def tier_sandbox_docker_memory(tier: str) -> str:
    return {"T0": "512m", "T1": "2g", "T2": "4g", "T3": "8g"}.get(tier, "512m")


def tier_sample_rows(tier: str) -> int:
    return {"T0": 0, "T1": 50_000, "T2": 100_000, "T3": 100_000}.get(tier, 0)


def parse_dataset_extra_metadata(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        import json
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def dataset_analysis_tier(ds: Any, file_size: Optional[int] = None) -> str:
    """从 Dataset 记录或文件大小推断 tier。"""
    meta = parse_dataset_extra_metadata(getattr(ds, "extra_metadata", None))
    tier = meta.get("analysis_tier")
    if tier in ("T0", "T1", "T2", "T3"):
        return tier
    size = file_size if file_size is not None else getattr(ds, "file_size", None)
    return resolve_analysis_tier(size)
