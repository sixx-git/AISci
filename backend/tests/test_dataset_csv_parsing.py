"""CSV 分隔符与 analyze_tabular_preview 回归测试。"""
from __future__ import annotations

import os
import tempfile

from unittest.mock import MagicMock

import pytest

from app.services.dataset_service import DatasetService


def _svc() -> DatasetService:
    return DatasetService(db=MagicMock())


SEMICOLON_CSV = """id;name;motivation
1;Alice;"Use federated learning, privacy, and collaboration"
2;Bob;"Research on data sharing; multi-site studies"
3;Carol;No commas here
"""


def test_read_tabular_dataframe_semicolon():
    svc = _svc()
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(SEMICOLON_CSV)
        path = f.name
    try:
        df = svc._read_tabular_dataframe(path)
        assert len(df) == 3
        assert list(df.columns) == ["id", "name", "motivation"]
    finally:
        os.remove(path)


def test_analyze_tabular_preview_semicolon_csv():
    duckdb = pytest.importorskip("duckdb")
    assert duckdb  # noqa: F841
    svc = _svc()
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(SEMICOLON_CSV)
        path = f.name
    try:
        result = svc.analyze_tabular_preview(path)
        assert result["n_rows"] == 3
        assert result["n_columns"] == 3
        assert "id" in result["columns"]
        assert result["preview"]
    finally:
        os.remove(path)


def test_analyze_tabular_preview_comma_csv_still_works():
    duckdb = pytest.importorskip("duckdb")
    assert duckdb  # noqa: F841
    svc = _svc()
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("a,b\n1,2\n3,4\n")
        path = f.name
    try:
        result = svc.analyze_tabular_preview(path)
        assert result["n_rows"] == 2
        assert result["n_columns"] == 2
    finally:
        os.remove(path)
