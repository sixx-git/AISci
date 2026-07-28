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


def test_moxie_like_key_join_uses_multiple_files(tmp_path: Path):
    """同目录多 schema、共享 sol 主键时，应按键合并多文件而非只留一张。"""
    a = tmp_path / "o2.csv"
    b = tmp_path / "run.csv"
    c = tmp_path / "telemetry.csv"
    d = tmp_path / "params.csv"  # 无 sol，可不纳入
    pd.DataFrame({"sol": [1, 2], "o2": [10.0, 20.0]}).to_csv(a, index=False)
    pd.DataFrame({"sol": [1, 2], "power": [1.5, 2.5]}).to_csv(b, index=False)
    pd.DataFrame({"sol": [1, 2, 3], "temp": [300, 310, 320]}).to_csv(c, index=False)
    pd.DataFrame({"parameter": ["x"], "value": [1.0]}).to_csv(d, index=False)

    pieces = [
        TablePiece(str(a), pd.read_csv(a)),
        TablePiece(str(b), pd.read_csv(b)),
        TablePiece(str(c), pd.read_csv(c)),
        TablePiece(str(d), pd.read_csv(d)),
    ]
    out = adaptive_combine_tables(pieces)
    meta = out.attrs.get("combine_meta") or {}
    assert meta.get("files_scanned") == 4
    assert len(out) >= 2
    assert "sol" in out.columns or out.shape[1] >= 2


def test_battery_like_does_not_collapse_to_few_rows(tmp_path: Path):
    """大时序表 + 小维表 + 稀疏时间戳交集时，不得被压成个位数行。"""
    # 大事实表
    fade = pd.DataFrame(
        {
            "battery_id": [f"B{i%5}" for i in range(200)],
            "cycle_index": list(range(200)),
            "capacity_Ahr": [1.0 + 0.01 * i for i in range(200)],
        }
    )
    # 维表
    meta = pd.DataFrame(
        {
            "battery_id": [f"B{i}" for i in range(5)],
            "group": ["g0", "g1", "g0", "g1", "g0"],
            "discharge_current_A": [1, 2, 1, 2, 1],
        }
    )
    # 仅 3 个时间戳重叠的脏表（旧逻辑会用 timestamp join 压成 3 行）
    cyc = pd.DataFrame(
        {
            "battery_id": ["B0", "B1", "B2"],
            "cycle_index": [0, 1, 2],
            "timestamp": [100, 200, 300],
            "V_mean": [3.1, 3.2, 3.3],
        }
    )
    eis = pd.DataFrame(
        {
            "battery_id": ["B0", "B1", "B2"],
            "cycle_index": [0, 1, 2],
            "timestamp": [100, 200, 300],
            "Re_ohm": [0.1, 0.2, 0.3],
        }
    )
    for name, df in (
        ("fade.csv", fade),
        ("meta.csv", meta),
        ("cyc.csv", cyc),
        ("eis.csv", eis),
    ):
        df.to_csv(tmp_path / name, index=False)

    pieces = [TablePiece(str(p), pd.read_csv(p)) for p in sorted(tmp_path.glob("*.csv"))]
    out = adaptive_combine_tables(pieces)
    assert len(out) >= 100, f"unexpected collapse to {len(out)} rows"
    assert out.select_dtypes("number").shape[1] >= 1
