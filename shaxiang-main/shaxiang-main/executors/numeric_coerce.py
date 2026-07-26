# -*- coding: utf-8 -*-
"""将「看起来像数字」的 object 列安全转为数值，增强 AutoDetect 泛用性。"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional

import pandas as pd

_PATH_LIKE = re.compile(
    r"\.(jpg|jpeg|png|gif|webp|bmp|wav|mp3|flac|ogg|m4a|csv|tsv|json|txt|parquet|rdata)\b",
    re.I,
)
_ID_NAME = re.compile(
    r"^(file_?path|filepath|path|filename|rel_?path|image|audio|subject|subj|id|uuid|name|study)$",
    re.I,
)
# 抽取首个完整数值；后面不能再跟字母/数字（避免 87Rb→8、75x→7）
_FIRST_NUMBER = re.compile(
    r"(?<![A-Za-z0-9])([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(?![A-Za-z0-9])"
)
_DATE_LIKE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}\b")
_MISSING_TOKENS = {
    "",
    "nan",
    "none",
    "null",
    "na",
    "n/a",
    "-",
    "—",
    "–",
    "/",
    "\\",
    ".",
    "?",
}
_KEY_COL_NAMES = frozenset(
    {"field", "parameter", "key", "metric", "property", "name", "attribute", "feature"}
)
_VALUE_COL_NAMES = frozenset(
    {"value", "val", "measurement", "measure", "amount", "quantity", "score"}
)
# 这些列即使偶尔含数字也不应被当成特征
_SKIP_COERCE_NAMES = frozenset(
    {
        "unit",
        "units",
        "source",
        "notes",
        "note",
        "comment",
        "comments",
        "description",
        "category",
        "access_date",
        "date",
        "url",
        "link",
        "doi",
        "ref",
        "reference",
    }
)


def count_numeric_columns(df: Optional[pd.DataFrame]) -> int:
    if df is None or df.empty:
        return 0
    num = df.select_dtypes(include=["number"])
    if num.empty:
        return 0
    # 全 NaN 的 float 列不算有效数值特征
    return int(sum(num[c].notna().any() for c in num.columns))


def _extract_first_number(text: str) -> Optional[str]:
    if text is None:
        return None
    s = str(text).strip().strip("\"'")
    if not s:
        return None
    low = s.lower()
    if low in _MISSING_TOKENS or low.startswith("not publicly") or low.startswith("not stated"):
        return None
    if _DATE_LIKE.match(s):
        return None
    # 归一化特殊减号/波浪；保留科学计数法 e
    s = (
        s.replace("\u00a0", " ")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("≈", " ")
        .replace("~", " ")
        .replace(",", "")
        .replace("%", "")
        .replace("×", "x")
    )
    m = _FIRST_NUMBER.search(s)
    if not m:
        return None
    return m.group(1)


def coerce_numeric_like_columns(
    df: pd.DataFrame,
    *,
    min_ratio: float = 0.65,
    skip_columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """把高比例可解析为数字的 object/string 列转为数值 dtype。

    - 跳过路径/文件名类列与明显 ID/标签列名
    - 支持从混杂单元格抽取首个数值（如 ``100 (Fresnel1)``、``0.90-0.98``）
    - 仅当非空值中可成功转换比例 ≥ min_ratio 才改写
    - 不破坏已是数值的列
    """
    if df is None or df.empty:
        return df

    out = df.copy()
    skip = {str(c) for c in (skip_columns or [])}

    # 顺带清理被引号包住的列名（IGT txt 常见）
    rename = {}
    for c in list(out.columns):
        s = str(c).strip()
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            rename[c] = s[1:-1].strip()
    if rename:
        out = out.rename(columns=rename)

    for col in list(out.columns):
        col_l = str(col).strip().lower()
        if str(col) in skip or col_l in _SKIP_COERCE_NAMES or _ID_NAME.match(str(col).strip()):
            continue
        series = out[col]
        if pd.api.types.is_numeric_dtype(series):
            continue
        if not (pd.api.types.is_object_dtype(series) or str(series.dtype) == "string"):
            continue

        non_null = series.dropna()
        if non_null.empty:
            continue

        sample = non_null.astype(str).head(30)
        if sample.map(lambda x: bool(_PATH_LIKE.search(x))).mean() >= 0.3:
            continue

        cleaned = series.map(_extract_first_number)
        numeric = pd.to_numeric(pd.Series(cleaned, index=series.index), errors="coerce")
        # 分母用「非空原始单元格」；缺失标记抽取为 None 不计入成功，但也不应拖垮「值」列
        ratio = float(numeric.notna().sum()) / float(len(non_null))
        # value / 厂商数值列允许更低阈值（硬件能力表常见）
        need = 0.55 if (
            col_l in _VALUE_COL_NAMES
            or col_l.endswith("_value")
            or "aquila" in col_l
            or "fresnel" in col_l
            or col_l in {"quera_aquila", "pasqal_fresnel"}
        ) else min_ratio
        if ratio >= need:
            out[col] = numeric

    return out


def numeric_column_names(df: Optional[pd.DataFrame]) -> List[str]:
    if df is None or df.empty:
        return []
    names: List[str] = []
    for c in df.select_dtypes(include=["number"]).columns:
        if df[c].notna().any():
            names.append(c)
    return names


def try_pivot_key_value_table(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """将 field/value 或 parameter + 数值列 的键值表透视为一行宽表。

    适用于硬件能力表、benchmark 规格表等「一行一个参数」的 CSV。
    失败或收益不大时返回 None。
    """
    if df is None or df.empty or len(df.columns) < 2:
        return None

    cols = list(df.columns)
    lower = {c: str(c).strip().lower() for c in cols}
    key_col = next((c for c in cols if lower[c] in _KEY_COL_NAMES), None)
    if key_col is None:
        return None

    # 优先经典 value 列；否则找可抽取数值的其它列
    value_cols = [c for c in cols if c != key_col and lower[c] in _VALUE_COL_NAMES]
    if not value_cols:
        candidates = []
        for c in cols:
            if c == key_col:
                continue
            if lower[c] in {"unit", "source", "notes", "note", "access_date", "category", "description"}:
                continue
            probe = coerce_numeric_like_columns(df[[c]], min_ratio=0.5)
            if count_numeric_columns(probe) >= 1:
                candidates.append(c)
        value_cols = candidates[:3]
    if not value_cols:
        return None

    keys = df[key_col].astype(str).str.strip()
    if keys.duplicated().mean() > 0.3:
        return None

    wide: dict = {}
    for vc in value_cols:
        series = coerce_numeric_like_columns(df[[vc]], min_ratio=0.5)[vc]
        prefix = "" if lower[vc] in _VALUE_COL_NAMES or len(value_cols) == 1 else f"{vc}__"
        for key, val in zip(keys, series):
            if not key or key.lower() in _MISSING_TOKENS:
                continue
            if pd.isna(val):
                continue
            safe = re.sub(r"[^\w.\-]+", "_", key)[:64]
            col_name = f"{prefix}{safe}" if prefix else safe
            if col_name in wide and pd.notna(wide[col_name]):
                continue
            wide[col_name] = val

    if not wide:
        return None
    out = pd.DataFrame([wide])
    # 透视结果已是数值标量，统一成数值 dtype
    for c in out.columns:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(axis=1, how="all")
    if count_numeric_columns(out) < 2:
        return None
    return out


def enrich_tabular_for_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """加载后增强：键值透视（若有收益）+ 数值强制转换。"""
    if df is None or df.empty:
        return df
    pivoted = try_pivot_key_value_table(df)
    base = coerce_numeric_like_columns(df)
    if pivoted is not None and count_numeric_columns(pivoted) > count_numeric_columns(base):
        return pivoted
    return base
