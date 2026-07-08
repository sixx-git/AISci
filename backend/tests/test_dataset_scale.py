"""数据集规模分级与探查相关测试。"""
from __future__ import annotations

import os
import tempfile

import pytest

from app.core.dataset_scale import resolve_analysis_tier, tier_sample_rows, tier_sandbox_timeout_sec
from app.services.data_probe_service import DataProbeService


def test_resolve_analysis_tier():
    assert resolve_analysis_tier(1024) == "T0"
    assert resolve_analysis_tier(60 * 1024 * 1024) == "T1"
    assert resolve_analysis_tier(600 * 1024 * 1024) == "T2"
    assert resolve_analysis_tier(3 * 1024 * 1024 * 1024) == "T3"


def test_tier_sandbox_timeout_increases():
    assert tier_sandbox_timeout_sec("T2") > tier_sandbox_timeout_sec("T0")
    assert tier_sample_rows("T2") > 0
    assert tier_sample_rows("T0") == 0


def test_duckdb_probe_small_csv():
    duckdb = pytest.importorskip("duckdb")
    assert duckdb  # noqa: F841
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("a,b\n1,2\n3,4\n5,6\n")
        path = f.name
    try:
        probe = DataProbeService().probe_tabular(path)
        assert probe.get("probe_status") == "completed"
        assert probe.get("n_rows") == 3
        assert "a" in (probe.get("columns") or [])
    finally:
        os.remove(path)
