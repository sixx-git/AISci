"""CSV 清洗 — 产出可回灌 merge 的 cleaned 文件"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def clean_csv_file(
    input_path: str,
    output_path: str,
    *,
    missing_strategy: str = "fill_median",
    drop_duplicates: bool = True,
) -> Dict[str, Any]:
    """清洗 tabular CSV，附加 _cleaning_action 列，返回 before/after 质量报告。"""
    if not input_path or not os.path.exists(input_path):
        raise FileNotFoundError(f"CSV 不存在: {input_path}")

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    before_rows = len(df)
    before_missing = int(df.isna().sum().sum())

    actions_log: List[str] = []
    row_actions: List[str] = []

    if drop_duplicates and before_rows > 0:
        dup_mask = df.duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            actions_log.append(f"removed_duplicate_rows={dup_count}")
            df = df[~dup_mask].copy()
        row_actions = ["dedup_kept"] * len(df)

    if len(df) == 0:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        pd.DataFrame(columns=list(df.columns) + ["_cleaning_action"]).to_csv(
            output_path, index=False, encoding="utf-8-sig"
        )
        return {
            "cleaned_csv_path": output_path,
            "rows_before": before_rows,
            "rows_after": 0,
            "missing_cells_before": before_missing,
            "missing_cells_after": 0,
            "actions": actions_log,
        }

    filled_cols: List[str] = []
    for col in df.columns:
        if col.startswith("_provenance_") or col == "_cleaning_action":
            continue
        missing_n = int(df[col].isna().sum())
        if missing_n == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            if missing_strategy == "drop_rows":
                df = df[df[col].notna()]
            else:
                fill_val = df[col].median()
                df[col] = df[col].fillna(fill_val)
                filled_cols.append(f"{col}:median")
        else:
            df[col] = df[col].fillna("unknown")
            filled_cols.append(f"{col}:unknown")

    if filled_cols:
        actions_log.append(f"missing_filled={';'.join(filled_cols[:8])}")

    if not row_actions or len(row_actions) != len(df):
        row_actions = ["cleaned"] * len(df)
    if filled_cols:
        row_actions = [
            (a + "|" + filled_cols[0][:40] if filled_cols else a) for a in row_actions
        ]

    df["_cleaning_action"] = row_actions[: len(df)]
    after_missing = int(df.isna().sum().sum())

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {
        "cleaned_csv_path": output_path,
        "rows_before": before_rows,
        "rows_after": len(df),
        "missing_cells_before": before_missing,
        "missing_cells_after": after_missing,
        "duplicate_removed": before_rows - len(df) if drop_duplicates else 0,
        "actions": actions_log,
        "missing_rate_before": round(before_missing / max(before_rows * max(len(df.columns), 1), 1), 4),
        "missing_rate_after": round(after_missing / max(len(df) * max(len(df.columns), 1), 1), 4),
    }


def infer_csv_schema(csv_path: str) -> Dict[str, Any]:
    """推断 CSV schema（列类型与描述）。"""
    if not os.path.exists(csv_path):
        return {"columns": []}
    df = pd.read_csv(csv_path, encoding="utf-8-sig", nrows=500)
    columns = []
    for col in df.columns:
        if col.startswith("_"):
            role = "metadata"
        else:
            role = "feature"
        dtype = str(df[col].dtype)
        columns.append({
            "name": col,
            "dtype": dtype,
            "role": role,
            "non_null_count": int(df[col].notna().sum()),
        })
    return {
        "row_count_sampled": len(df),
        "column_count": len(columns),
        "columns": columns,
    }
