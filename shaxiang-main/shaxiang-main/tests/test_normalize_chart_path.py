"""图表路径归一化：脚本把图存到仓库根时，应复制进 chart_dir。"""
from pathlib import Path

from executors.sandbox import normalize_chart_path


def test_normalize_chart_path_copies_orphan(tmp_path: Path):
    chart_dir = tmp_path / "data" / "charts" / "smoke"
    orphan = tmp_path / "ts_pred.png"
    orphan.write_bytes(b"png-bytes")

    out = normalize_chart_path(str(orphan), chart_dir)
    assert out is not None
    dest = Path(out)
    assert dest.is_file()
    assert dest.parent.resolve() == chart_dir.resolve()
    assert dest.name == "ts_pred.png"
    assert dest.read_bytes() == b"png-bytes"


def test_normalize_chart_path_keeps_in_dir(tmp_path: Path):
    chart_dir = tmp_path / "charts"
    chart_dir.mkdir(parents=True)
    src = chart_dir / "a.png"
    src.write_bytes(b"x")
    out = normalize_chart_path(str(src), chart_dir)
    assert Path(out).resolve() == src.resolve()
