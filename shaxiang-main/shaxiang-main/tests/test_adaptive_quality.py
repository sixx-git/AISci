"""自适应多表合并 + 质量模式门禁测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core.quality_mode import apply_quality_mode_to_decision, is_round_acceptable
from executors.adaptive_table_combine import TablePiece, adaptive_combine_tables
from executors.data_adapter import DataConfig
from executors.dataset_profile import DatasetProfile
from executors.directory_loader import DirectoryLoader
from schemas.analysis import AnalysisReport, IterationDecision


def test_adaptive_combine_horizontal_then_vertical(tmp_path: Path):
    # 模拟互补矩阵（同 nrows）+ 另一 cohort
    pd.DataFrame({"a1": [1, 2], "a2": [3, 4]}).to_csv(tmp_path / "feat_2.csv", index=False)
    pd.DataFrame({"b1": [5, 6], "b2": [7, 8]}).to_csv(tmp_path / "lab_2.csv", index=False)
    pd.DataFrame({"a1": [9], "a2": [10]}).to_csv(tmp_path / "feat_1.csv", index=False)
    pd.DataFrame({"b1": [11], "b2": [12]}).to_csv(tmp_path / "lab_1.csv", index=False)

    pieces = []
    for p in sorted(tmp_path.glob("*.csv")):
        pieces.append(TablePiece(path=str(p), df=pd.read_csv(p)))
    out = adaptive_combine_tables(pieces)
    assert not out.empty
    # 应横拼出 a* + b*，并竖拼两个 cohort → 3 行
    assert len(out) == 3
    assert {"a1", "a2", "b1", "b2"}.issubset(set(out.columns))
    assert float(out.isna().mean().mean()) < 0.01


def test_adaptive_loader_on_igt_like_directory_if_present():
    root = Path(r"D:\浏览器\报告汇总\sjtu_q_125_智能机器预测未来\data\IGTdataSteingroever2014")
    if not root.is_dir():
        return
    profile = DatasetProfile(
        name="Auto",
        modality="tabular",
        scan_pattern="**/*.csv",
        file_extensions=[".csv"],
        delimiter=",",
        has_header=True,
    )
    cfg = DataConfig(
        source_type="directory",
        source_path=str(root),
        profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
    )
    loaded = DirectoryLoader().load(cfg)
    # 自适应应远好于盲目竖拼（~82% 空值）
    assert len(loaded) >= 500
    assert float(loaded.isna().mean().mean()) < 0.45


def test_draft_accepts_needs_adjustment_with_charts():
    assert is_round_acceptable(
        quality_mode="draft",
        execution_status="success",
        overall_assessment="needs_adjustment",
        has_charts=True,
    )
    assert not is_round_acceptable(
        quality_mode="draft",
        execution_status="success",
        overall_assessment="significant_issue",
        has_charts=True,
    )
    assert not is_round_acceptable(
        quality_mode="strict",
        execution_status="success",
        overall_assessment="needs_adjustment",
        has_charts=True,
    )


def test_apply_quality_mode_stops_on_draft_needs_adjustment():
    analysis = AnalysisReport(overall_assessment="needs_adjustment", summary="ok")
    decision = IterationDecision(should_continue=True)
    result = type("R", (), {"status": "success", "raw_output": {"chart_paths": ["a.png"]}})()
    out = apply_quality_mode_to_decision(
        quality_mode="draft",
        analysis=analysis,
        decision=decision,
        result=result,
    )
    assert out.should_continue is False
