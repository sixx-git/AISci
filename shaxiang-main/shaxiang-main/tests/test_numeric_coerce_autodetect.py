# -*- coding: utf-8 -*-
"""Tests for numeric coercion + AutoDetect adaptive recovery."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from executors.numeric_coerce import coerce_numeric_like_columns, count_numeric_columns
from executors.adaptive_table_combine import _score, adaptive_combine_tables, TablePiece


def test_coerce_numeric_like_object_columns():
    df = pd.DataFrame(
        {
            "a": ["1", "2", "3"],
            "b": ['"4.5"', '"5.5"', '"6.5"'],
            "label": ["A", "B", "A"],
            "path": ["x.png", "y.png", "z.png"],
        }
    )
    out = coerce_numeric_like_columns(df)
    assert count_numeric_columns(out) == 2
    assert pd.api.types.is_numeric_dtype(out["a"])
    assert pd.api.types.is_numeric_dtype(out["b"])
    assert out["label"].dtype == object or str(out["label"].dtype) == "string"
    assert not pd.api.types.is_numeric_dtype(out["path"])


def test_coerce_strips_quoted_column_names():
    df = pd.DataFrame({'"Choice_1"': ["1", "2"], '"Choice_2"': ["3", "4"]})
    out = coerce_numeric_like_columns(df)
    assert "Choice_1" in out.columns
    assert count_numeric_columns(out) == 2


def test_combine_score_prefers_numeric_wide_table():
    index_df = pd.DataFrame({"Subj": ["s1", "s2"], "Study": ["A", "B"]})
    wide_df = pd.DataFrame({f"c{i}": list(range(2)) for i in range(20)})
    assert _score(wide_df) > _score(index_df)

    pieces = [
        TablePiece(path="index.csv", df=index_df),
        TablePiece(path="wide.csv", df=wide_df),
    ]
    combined = adaptive_combine_tables(pieces)
    assert count_numeric_columns(combined) >= 10


def test_verify_recovers_when_profile_points_to_empty_ext(tmp_path: Path):
    """故意给错误扩展名时，verify 应回退到 csv 并找到数值列。"""
    from services.experiment_service import ExperimentService

    # 造一个小 csv 目录
    root = tmp_path / "data"
    root.mkdir()
    pd.DataFrame({"f1": [1.0, 2.0, 3.0], "f2": [0.1, 0.2, 0.3], "label": [0, 1, 0]}).to_csv(
        root / "part.csv", index=False
    )

    bad_profile = {
        "name": "bad",
        "modality": "tabular",
        "scan_pattern": "**/*.rdata",
        "file_extensions": [".rdata"],
        "delimiter": ",",
        "has_header": True,
    }
    cfg = {
        "source_type": "directory",
        "source_path": str(root),
        "profile_name": "AutoDetect",
        "profile_json": json.dumps(bad_profile),
        "sample_size": 100,
    }

    svc = ExperimentService.__new__(ExperimentService)
    # _recover 不依赖完整 init
    recovered = ExperimentService._recover_tabular_numeric_profile(svc, cfg, sample_size=100)
    assert recovered is not None
    meta, profile = recovered
    assert len(meta.get("numeric_columns") or []) >= 2
    assert ".csv" in (profile.get("file_extensions") or [])


def test_verify_data_config_recovers_end_to_end(tmp_path: Path):
    from services.experiment_service import ExperimentService

    root = tmp_path / "igt_like"
    root.mkdir()
    # 数字以字符串写入，模拟 object 列
    pd.DataFrame(
        {
            "Choice_1": ["1", "2", "1"],
            "Choice_2": ["3", "4", "2"],
            "Wins_1": ["10", "20", "30"],
        }
    ).to_csv(root / "choice.csv", index=False)
    # 额外写一个几乎无用的 index
    pd.DataFrame({"Subj": ["a", "b", "c"], "Study": ["X", "Y", "Z"]}).to_csv(
        root / "index.csv", index=False
    )

    bad_profile = {
        "name": "bad_rdata",
        "modality": "tabular",
        "scan_pattern": "**/*",
        "file_extensions": [".rdata"],
        "delimiter": ",",
        "has_header": True,
    }
    cfg = {
        "source_type": "directory",
        "source_path": str(root),
        "profile_name": "AutoDetect",
        "profile_json": json.dumps(bad_profile),
        "sample_size": 50,
    }
    svc = ExperimentService.__new__(ExperimentService)
    out = ExperimentService.verify_data_config(svc, cfg, sample_size=50)
    assert out.get("ok") is True
    assert len(out.get("numeric_columns") or []) >= 2
    assert out.get("profile_recovered") is True


def test_verify_recovers_despite_polluted_llm_profile(tmp_path: Path):
    """LLM 误判为 image 且带 skip_rows 时，回退不得继承这些字段。"""
    from services.experiment_service import ExperimentService

    root = tmp_path / "eis_like"
    root.mkdir()
    pd.DataFrame(
        {"freq": [1.0, 2.0, 3.0], "zreal": [10.0, 20.0, 30.0], "zimag": [-1.0, -2.0, -3.0]}
    ).to_csv(root / "sample.csv", index=False)

    bad_profile = {
        "name": "LLM_bad",
        "modality": "image",
        "scan_pattern": "**/*",
        "file_extensions": [".png", ".rdata"],
        "delimiter": ",",
        "has_header": True,
        "skip_rows": 999,
        "comment_prefix": '"',
    }
    cfg = {
        "source_type": "directory",
        "source_path": str(root),
        "profile_name": "AutoDetect",
        "profile_json": json.dumps(bad_profile),
        "sample_size": 50,
    }
    svc = ExperimentService.__new__(ExperimentService)
    out = ExperimentService.verify_data_config(svc, cfg, sample_size=50)
    assert out.get("ok") is True
    assert len(out.get("numeric_columns") or []) >= 2
    assert out.get("profile_recovered") is True
    assert (out.get("recovered_profile") or {}).get("skip_rows", 0) in (0, None)
