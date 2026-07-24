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


def count_numeric_columns(df: Optional[pd.DataFrame]) -> int:
    if df is None or df.empty:
        return 0
    return int(df.select_dtypes(include=["number"]).shape[1])


def coerce_numeric_like_columns(
    df: pd.DataFrame,
    *,
    min_ratio: float = 0.75,
    skip_columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """把高比例可解析为数字的 object/string 列转为数值 dtype。

    - 跳过路径/文件名类列与明显 ID/标签列名
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
        if str(col) in skip or _ID_NAME.match(str(col).strip()):
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

        cleaned = (
            series.astype(str)
            .str.strip()
            .str.strip("\"'")
            .str.replace("\u00a0", " ", regex=False)
            .str.replace("%", "", regex=False)  # 15.40% → 15.40
            .str.replace(",", "", regex=False)  # 千分位
        )
        # 空串 / 常见缺失标记 → NA
        cleaned = cleaned.replace(
            {"": pd.NA, "nan": pd.NA, "None": pd.NA, "null": pd.NA, "NA": pd.NA, "N/A": pd.NA},
        )
        numeric = pd.to_numeric(cleaned, errors="coerce")
        ratio = float(numeric.notna().sum()) / float(len(non_null))
        if ratio >= min_ratio:
            out[col] = numeric

    return out


def numeric_column_names(df: Optional[pd.DataFrame]) -> List[str]:
    if df is None or df.empty:
        return []
    return list(df.select_dtypes(include=["number"]).columns)
