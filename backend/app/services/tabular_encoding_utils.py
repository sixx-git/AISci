"""表格数据编码 — 将分类/序数列转为数值，供 pilot 与沙箱分析使用。"""
from __future__ import annotations

import os
import re
from typing import List, Optional

import pandas as pd


def read_tabular_file(file_path: str, *, nrows: Optional[int] = None) -> pd.DataFrame:
    """读取 CSV/TSV（含分号分隔），与 DatasetService 预处理逻辑一致。"""
    from app.services.dataset_service import DatasetService

    return DatasetService._read_tabular_dataframe(file_path, nrows=nrows)


def build_sandbox_load_data_preamble() -> str:
    """沙箱内 _aisci_load_data：多分隔符 CSV 读取（注入到 analysis.py 头部）。"""
    return (
        "def _aisci_guess_csv_sep(path):\n"
        "    try:\n"
        "        with open(path, 'r', encoding='utf-8', errors='replace') as fh:\n"
        "            header = fh.readline()\n"
        "    except OSError:\n"
        "        return None\n"
        "    if not header.strip():\n"
        "        return None\n"
        "    cands = [(';', header.count(';')), (',', header.count(',')), ('\\t', header.count('\\t')), ('|', header.count('|'))]\n"
        "    best_sep, best_count = max(cands, key=lambda item: item[1])\n"
        "    return best_sep if best_count > 0 else None\n"
        "\n"
        "def _aisci_read_csv(path, nrows=None):\n"
        "    import pandas as pd\n"
        "    kwargs = {'nrows': nrows} if nrows else {}\n"
        "    guessed = _aisci_guess_csv_sep(path)\n"
        "    attempts = []\n"
        "    if guessed:\n"
        "        attempts.append({'sep': guessed})\n"
        "    attempts.extend([{}, {'sep': ';'}, {'sep': '\\t'}, {'sep': '|'}, {'sep': None, 'engine': 'python'}])\n"
        "    seen = set()\n"
        "    best_df = None\n"
        "    last_error = None\n"
        "    for extra in attempts:\n"
        "        key = tuple(sorted(extra.items()))\n"
        "        if key in seen:\n"
        "            continue\n"
        "        seen.add(key)\n"
        "        try:\n"
        "            df = pd.read_csv(path, **kwargs, **extra)\n"
        "            if len(df.columns) <= 1 and guessed and extra.get('sep') != guessed:\n"
        "                continue\n"
        "            if best_df is None or len(df.columns) > len(best_df.columns):\n"
        "                best_df = df\n"
        "            if len(df.columns) > 1:\n"
        "                return df\n"
        "        except Exception as exc:\n"
        "            last_error = exc\n"
        "    if best_df is not None:\n"
        "        return best_df\n"
        "    if last_error:\n"
        "        raise last_error\n"
        "    raise ValueError('无法解析 CSV: ' + str(path))\n"
        "\n"
        "def _aisci_load_data():\n"
        "    import os\n"
        "    path = os.environ.get('AISCI_DATA_PATH') or os.environ.get('CSV_DATA_PATH') or ''\n"
        "    if not path:\n"
        "        raise FileNotFoundError('沙箱未注入 AISCI_DATA_PATH')\n"
        "    tier = os.environ.get('AISCI_DATA_TIER', 'T0')\n"
        "    sample_pq = os.environ.get('AISCI_SAMPLE_PARQUET') or ''\n"
        "    nrows = int(os.environ.get('AISCI_SAMPLE_ROWS') or '0')\n"
        "    if tier in ('T1', 'T2', 'T3') and sample_pq and os.path.exists(sample_pq):\n"
        "        import pandas as pd\n"
        "        return pd.read_parquet(sample_pq)\n"
        "    if tier in ('T1', 'T2', 'T3') and nrows > 0:\n"
        "        return _aisci_read_csv(path, nrows=nrows)\n"
        "    return _aisci_read_csv(path)\n"
        "\n"
    )


_PRESENT_ABSENT = {
    "present": 1.0,
    "absent": 0.0,
    "yes": 1.0,
    "no": 0.0,
    "true": 1.0,
    "false": 0.0,
    "positive": 1.0,
    "negative": 0.0,
}

_OUTCOME_NAME_HINTS = (
    "carcinoma",
    "label",
    "target",
    "outcome",
    "class",
    "jaundice",
    "fibrosis",
    "cirrhosis",
    "mortality",
    "death",
)


def parse_ordinal_token(val: object) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    v = str(val).strip().lower()
    if v in _PRESENT_ABSENT:
        return _PRESENT_ABSENT[v]
    m = re.match(r"^a(\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)$", v)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2.0
    m = re.match(r"^age(\d+)_(\d+)$", v)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2.0
    return None


def encode_tabular_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """将 object/分类列编码为数值；已是数值的列保留。"""
    if frame is None or frame.empty:
        return frame
    out = {}
    for col in frame.columns:
        series = frame[col]
        if pd.api.types.is_numeric_dtype(series):
            out[col] = pd.to_numeric(series, errors="coerce")
            continue
        parsed = series.astype(str).str.strip().str.lower().map(parse_ordinal_token)
        if parsed.notna().mean() >= 0.5:
            out[col] = parsed.astype(float)
            continue
        codes, _ = pd.factorize(series.astype(str))
        out[col] = pd.Series(codes, index=series.index).astype(float)
    encoded = pd.DataFrame(out)
    return encoded.dropna(axis=1, how="all")


def pick_value_column(frame: pd.DataFrame, *, prefer_names: Optional[List[str]] = None) -> Optional[str]:
    """选择用于 pilot/默认脚本的数值列。"""
    if frame is None or frame.empty:
        return None
    hints = tuple(prefer_names or ()) + _OUTCOME_NAME_HINTS
    numeric_cols = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
    if not numeric_cols:
        return None
    for hint in hints:
        for col in numeric_cols:
            if hint in str(col).lower():
                if frame[col].notna().sum() >= 10:
                    return col
    best_col = None
    best_std = -1.0
    for col in numeric_cols:
        vals = frame[col].dropna()
        if len(vals) < 10:
            continue
        std = float(vals.std()) if len(vals) > 1 else 0.0
        if std > best_std:
            best_std = std
            best_col = col
    return best_col or (numeric_cols[0] if numeric_cols else None)


def build_sandbox_encode_preamble() -> str:
    """注入沙箱脚本的编码辅助函数（与 encode_tabular_frame 逻辑一致）。"""
    return (
        "def _aisci_parse_token(val):\n"
        "    import re\n"
        "    if val is None:\n"
        "        return None\n"
        "    try:\n"
        "        if isinstance(val, (int, float)) and not isinstance(val, bool):\n"
        "            return float(val)\n"
        "    except Exception:\n"
        "        pass\n"
        "    v = str(val).strip().lower()\n"
        "    mapping = {'present': 1.0, 'absent': 0.0, 'yes': 1.0, 'no': 0.0}\n"
        "    if v in mapping:\n"
        "        return mapping[v]\n"
        "    m = re.match(r'^a(\\\\d+(?:\\\\.\\\\d+)?)_(\\\\d+(?:\\\\.\\\\d+)?)$', v)\n"
        "    if m:\n"
        "        return (float(m.group(1)) + float(m.group(2))) / 2.0\n"
        "    m = re.match(r'^age(\\\\d+)_(\\\\d+)$', v)\n"
        "    if m:\n"
        "        return (float(m.group(1)) + float(m.group(2))) / 2.0\n"
        "    return None\n"
        "\n"
        "def _aisci_encode_frame(df):\n"
        "    import pandas as pd\n"
        "    out = {}\n"
        "    for col in df.columns:\n"
        "        s = df[col]\n"
        "        if hasattr(s, 'dtype') and str(getattr(s.dtype, 'kind', '')) in 'iufc':\n"
        "            out[col] = pd.to_numeric(s, errors='coerce')\n"
        "            continue\n"
        "        parsed = s.astype(str).str.strip().str.lower().map(_aisci_parse_token)\n"
        "        if parsed.notna().mean() >= 0.5:\n"
        "            out[col] = parsed.astype(float)\n"
        "            continue\n"
        "        codes, _ = pd.factorize(s.astype(str))\n"
        "        out[col] = pd.Series(codes, index=s.index).astype(float)\n"
        "    enc = pd.DataFrame(out).dropna(axis=1, how='all')\n"
        "    return enc if not enc.empty else df\n"
        "\n"
    )
