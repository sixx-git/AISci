"""建模 Skill 共享工具"""
from __future__ import annotations

import base64
import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TARGET_COLUMN_KEYWORDS = [
    "label", "target", "class", "y", "accuracy", "score", "result", "outcome",
    "行为", "类别", "标签", "准确率", "评分", "目标", "结果", "分类",
    "diagnosis", "prognosis", "response", "status", "flag",
]

MAX_TRAIN_ROWS = 5000
PILOT_VALIDATION_ROW_THRESHOLD = 500


def require_ml_libs():
    try:
        import pandas as pd  # noqa: F401
        import numpy as np  # noqa: F401
        from sklearn.model_selection import train_test_split  # noqa: F401
        return True
    except ImportError as exc:
        raise ImportError(
            "建模功能需要 pandas、numpy、scikit-learn，请执行 pip install pandas numpy scikit-learn"
        ) from exc


def load_dataframe(file_path: str):
    require_ml_libs()
    import pandas as pd

    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"数据文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    if ext == ".json":
        return pd.read_json(file_path)
    if ext == ".jsonl":
        return pd.read_json(file_path, lines=True)
    return pd.read_csv(file_path)


def infer_target_candidates(columns: List[str]) -> List[str]:
    candidates: List[str] = []
    for col in columns:
        col_l = col.lower()
        if any(k in col_l for k in TARGET_COLUMN_KEYWORDS):
            candidates.append(col)
    return candidates


def split_feature_target(df, target_column: str):
    if target_column not in df.columns:
        raise ValueError(f"目标列不存在: {target_column}")
    X = df.drop(columns=[target_column])
    y = df[target_column]
    return X, y


def is_numeric_series(series) -> bool:
    import pandas as pd

    return pd.api.types.is_numeric_dtype(series)


def is_categorical_series(series) -> bool:
    import pandas as pd

    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
        or pd.api.types.is_bool_dtype(series)
        or pd.api.types.is_categorical_dtype(series)
    )


def sample_dataframe(df, max_rows: int = MAX_TRAIN_ROWS):
    if len(df) <= max_rows:
        return df, False
    return df.sample(n=max_rows, random_state=42), True


def figure_to_chart_entry(title: str, chart_type: str, fig, plot_id: str) -> Dict[str, Any]:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return {
        "plot_id": plot_id,
        "title": title,
        "type": chart_type,
        "base64": encoded,
        "is_generated_from_real_data": True,
        "description": title,
    }


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        val = float(value)
        if val != val:  # NaN
            return None
        return round(val, 6)
    except (TypeError, ValueError):
        return None
