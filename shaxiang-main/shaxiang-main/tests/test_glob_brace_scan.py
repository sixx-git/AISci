"""Tests for brace-aware directory scanning / AutoDetect repair."""
from __future__ import annotations

import json
from pathlib import Path

from core.dataset_profiler import DatasetProfiler
from executors.data_adapter import DataConfig
from executors.dataset_profile import DatasetProfile
from executors.directory_loader import DirectoryLoader
from executors.glob_utils import expand_brace_globs, glob_files


def test_expand_brace_globs():
    assert expand_brace_globs("**/*.{csv,txt}") == ["**/*.csv", "**/*.txt"]
    assert expand_brace_globs("**/*.csv") == ["**/*.csv"]
    assert expand_brace_globs("**/*.{jpg,png,jpeg}") == ["**/*.jpg", "**/*.png", "**/*.jpeg"]


def test_glob_files_brace_on_igt_like(tmp_path: Path):
    (tmp_path / "choice_100.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "choice_100.txt").write_text("a b\n1 2\n", encoding="utf-8")
    hits = glob_files(tmp_path, "**/*.{csv,txt}")
    assert len(hits) == 2
    hits_csv = glob_files(tmp_path, "**/*.{csv,txt}", [".csv"])
    assert len(hits_csv) == 1
    assert hits_csv[0].name == "choice_100.csv"


def test_directory_loader_accepts_brace_scan_pattern(tmp_path: Path):
    (tmp_path / "choice_100.csv").write_text(
        '"Choice_1","Choice_2"\n"1","2"\n', encoding="utf-8"
    )
    profile = DatasetProfile(
        name="IGT_like",
        modality="tabular",
        scan_pattern="**/*.{csv,txt}",
        file_extensions=[".csv", ".txt"],
        delimiter=",",
        has_header=True,
    )
    cfg = DataConfig(
        source_type="directory",
        source_path=str(tmp_path),
        profile_name="",
        profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
    )
    loaded = DirectoryLoader().load(cfg)
    assert not loaded.empty
    assert "Choice_1" in loaded.columns


def test_ensure_scan_matches_repairs_empty_brace(tmp_path: Path):
    (tmp_path / "a.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    profiler = DatasetProfiler(llm_client=None)  # type: ignore[arg-type]
    profile = DatasetProfile(
        name="bad",
        modality="tabular",
        scan_pattern="**/*.{csv,txt}",
        file_extensions=[],
        delimiter=",",
        has_header=False,
    )
    inventory = {
        "counts": {"tabular": 1},
        "examples": {"tabular": ["a.csv"]},
        "guessed_modality": "tabular",
    }
    fixed = profiler._ensure_scan_matches(profile, tmp_path, inventory)
    hits = glob_files(tmp_path, fixed.scan_pattern, fixed.file_extensions)
    assert hits, f"still empty after repair: {fixed.scan_pattern} {fixed.file_extensions}"


def test_real_igt_directory_if_present():
    root = Path(r"D:\浏览器\报告汇总\sjtu_q_125_智能机器预测未来\data\IGTdataSteingroever2014")
    if not root.is_dir():
        return
    assert glob_files(root, "**/*.{csv,txt}", [".csv"])
    profile = DatasetProfile(
        name="IGT",
        modality="tabular",
        scan_pattern="**/*.csv",
        file_extensions=[".csv"],
        delimiter=",",
        has_header=True,
        exclude_patterns=[r"^\.DS_Store$", r"\.rdata$"],
    )
    cfg = DataConfig(
        source_type="directory",
        source_path=str(root),
        profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
    )
    loaded = DirectoryLoader().load(cfg)
    assert not loaded.empty
    assert loaded.shape[1] > 2, f"应横拼 choice/wi/lo，不应只剩 index: {list(loaded.columns)}"
    assert any(str(c).startswith(("Choice_", "Choice_", "Wins_", "Losses_")) for c in loaded.columns)
    assert float(loaded.isna().mean().mean()) < 0.45


def test_ensure_scan_falls_back_from_rdata(tmp_path: Path):
    """LLM 误扫 .rdata 时，应回退到可解析的 .csv。"""
    (tmp_path / "IGTdata.rdata").write_bytes(b"R binary placeholder")
    (tmp_path / "choice_100.csv").write_text(
        '"Choice_1","Choice_2"\n"Subj_1",1,2\n', encoding="utf-8"
    )
    profiler = DatasetProfiler(llm_client=None)  # type: ignore[arg-type]
    profile = DatasetProfile(
        name="rdata_only",
        modality="tabular",
        scan_pattern="**/*.rdata",
        file_extensions=[".rdata"],
        delimiter=",",
        has_header=True,
    )
    inventory = {
        "counts": {"tabular": 1},
        "examples": {"tabular": ["choice_100.csv"]},
        "guessed_modality": "tabular",
    }
    fixed = profiler._ensure_scan_matches(profile, tmp_path, inventory)
    assert ".csv" in (fixed.file_extensions or []) or (fixed.scan_pattern or "").endswith(".csv")
    hits = glob_files(tmp_path, fixed.scan_pattern, fixed.file_extensions)
    assert hits and all(h.suffix.lower() == ".csv" for h in hits)
    cfg = DataConfig(
        source_type="directory",
        source_path=str(tmp_path),
        profile_json=json.dumps(fixed.to_dict(), ensure_ascii=False),
    )
    loaded = DirectoryLoader().load(cfg)
    assert not loaded.empty
    assert "Choice_1" in loaded.columns


def test_prefer_csv_twins_over_space_txt(tmp_path: Path):
    """同 stem 的 csv(逗号) / txt(空格) 并存时，AutoDetect 应改扫 csv。"""
    (tmp_path / "choice_95.csv").write_text(
        '"Choice_1","Choice_2"\n"Subj_1",1,2\n', encoding="utf-8"
    )
    (tmp_path / "choice_95.txt").write_text(
        '"Choice_1" "Choice_2"\n"Subj_1" 1 2\n', encoding="utf-8"
    )
    profiler = DatasetProfiler(llm_client=None)  # type: ignore[arg-type]
    profile = DatasetProfile(
        name="txt_only",
        modality="tabular",
        scan_pattern="**/*.txt",
        file_extensions=[".txt"],
        delimiter=",",
        has_header=True,
    )
    inventory = {
        "counts": {"tabular": 2},
        "examples": {"tabular": ["choice_95.csv", "choice_95.txt"]},
        "guessed_modality": "tabular",
    }
    fixed = profiler._ensure_scan_matches(profile, tmp_path, inventory)
    assert fixed.file_extensions == [".csv"]
    assert fixed.delimiter == ","
    cfg = DataConfig(
        source_type="directory",
        source_path=str(tmp_path),
        profile_json=json.dumps(fixed.to_dict(), ensure_ascii=False),
    )
    loaded = DirectoryLoader().load(cfg)
    assert not loaded.empty
    assert "Choice_1" in loaded.columns


def test_read_file_fallback_space_separated_txt(tmp_path: Path):
    (tmp_path / "a.txt").write_text(
        '"A" "B"\n"1" "2"\n', encoding="utf-8"
    )
    profile = DatasetProfile(
        name="space_txt",
        modality="tabular",
        scan_pattern="**/*.txt",
        file_extensions=[".txt"],
        delimiter=",",  # 故意错误
        has_header=True,
    )
    cfg = DataConfig(
        source_type="directory",
        source_path=str(tmp_path),
        profile_json=json.dumps(profile.to_dict(), ensure_ascii=False),
    )
    loaded = DirectoryLoader().load(cfg)
    assert not loaded.empty
    assert loaded.shape[1] >= 2


def test_engine_config_repair_attempts_default_10():
    from core.engine import EngineConfig

    assert EngineConfig().max_script_repair_attempts == 10
    cfg = EngineConfig.from_env()
    assert cfg.max_script_repair_attempts == 10
