"""文本型 / 二进制 .dat 的 AutoDetect 读取行为。"""
import json
from pathlib import Path

import pytest

from executors.data_adapter import DataConfig
from executors.directory_loader import (
    DirectoryLoader,
    _BINARY_DAT_MSG,
    looks_like_text_tabular_file,
)
from executors.dataset_profile import DatasetProfile


def _profile_dat(*, delimiter: str = r"\s+", has_header: bool = True) -> DatasetProfile:
    return DatasetProfile(
        name="Heuristic_dat_test",
        modality="tabular",
        scan_pattern="**/*.dat",
        file_extensions=[".dat"],
        delimiter=delimiter,
        has_header=has_header,
        exclude_patterns=[],
    )


def test_looks_like_text_tabular_space_dat(tmp_path: Path):
    p = tmp_path / "a.dat"
    p.write_text("x y z\n1 2 3\n4 5 6\n", encoding="utf-8")
    assert looks_like_text_tabular_file(p) is True


def test_looks_like_binary_dat(tmp_path: Path):
    p = tmp_path / "raw.dat"
    p.write_bytes(bytes(range(256)) * 8)
    assert looks_like_text_tabular_file(p) is False


def test_read_text_dat_space(tmp_path: Path):
    p = tmp_path / "table.dat"
    p.write_text("a b c\n1.0 2.0 3.0\n4.0 5.0 6.0\n", encoding="utf-8")
    loader = DirectoryLoader()
    df = loader._read_file(p, _profile_dat(delimiter=r"\s+", has_header=True))
    assert df is not None
    assert list(df.columns) == ["a", "b", "c"]
    assert df.shape[0] == 2
    assert df.select_dtypes(include="number").shape[1] >= 2


def test_read_text_dat_comma(tmp_path: Path):
    p = tmp_path / "table.dat"
    p.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    loader = DirectoryLoader()
    df = loader._read_file(p, _profile_dat(delimiter=",", has_header=True))
    assert df is not None
    assert df.shape == (2, 3)


def test_read_binary_dat_raises(tmp_path: Path):
    p = tmp_path / "raw.dat"
    p.write_bytes(b"\x00\x01\x02\x03" * 256)
    loader = DirectoryLoader()
    with pytest.raises(ValueError, match="二进制 .dat"):
        loader._read_file(p, _profile_dat())


def test_load_directory_text_dat(tmp_path: Path):
    (tmp_path / "x.dat").write_text("f1 f2 label\n0.1 0.2 0\n0.3 0.4 1\n", encoding="utf-8")
    profile = _profile_dat(delimiter=r"\s+", has_header=True)
    cfg = DataConfig(
        source_type="directory",
        source_path=str(tmp_path),
        profile_json=json.dumps(profile.to_dict()),
    )
    df = DirectoryLoader().load(cfg)
    assert not df.empty
    assert df.select_dtypes(include="number").shape[1] >= 2


def test_load_directory_binary_dat_clear_error(tmp_path: Path):
    (tmp_path / "raw.dat").write_bytes(bytes([0, 1, 2, 255, 128]) * 200)
    profile = _profile_dat()
    cfg = DataConfig(
        source_type="directory",
        source_path=str(tmp_path),
        profile_json=json.dumps(profile.to_dict()),
    )
    with pytest.raises(ValueError) as ei:
        DirectoryLoader().load(cfg)
    assert "二进制 .dat" in str(ei.value)
    assert _BINARY_DAT_MSG[:20] in str(ei.value)
