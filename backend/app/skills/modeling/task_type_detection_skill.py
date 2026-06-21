"""任务类型识别 Skill"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.skills.base import BaseSkill, SkillResult
from app.skills.modeling._utils import is_categorical_series, is_numeric_series, load_dataframe


class TaskTypeDetectionSkill(BaseSkill):
    name = "TaskTypeDetection"
    description = "识别分类/回归/时序/未知任务类型"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        target_column = input_data.get("target_column", "")
        user_task_type = (input_data.get("task_type") or "").strip().lower()
        profile = input_data.get("profile", {})
        csv_path = input_data.get("csv_path") or input_data.get("file_path", "")

        allowed = {"classification", "regression", "time_series", "unknown"}
        if user_task_type in allowed - {"unknown"}:
            result.data = {
                "task_type": user_task_type,
                "target_column": target_column,
                "detection_source": "user_selected",
                "reason": f"用户指定任务类型: {user_task_type}",
            }
            return result

        try:
            df = load_dataframe(csv_path)
        except Exception as exc:
            result.add_error(str(exc))
            return result

        if target_column not in df.columns:
            result.add_error(f"目标列不存在: {target_column}")
            return result

        y = df[target_column]
        task_type = "unknown"
        reason = "无法根据目标变量推断任务类型"

        datetime_cols = [
            col for col in df.columns
            if str(df[col].dtype).startswith("datetime") or col.lower() in {"date", "time", "timestamp", "datetime"}
        ]
        if datetime_cols or str(getattr(df.index, "dtype", "")).startswith("datetime"):
            task_type = "time_series"
            reason = "检测到时间列或时间索引，判定为 time_series"
        elif is_categorical_series(y) or y.nunique(dropna=True) <= 20:
            task_type = "classification"
            reason = f"目标列 `{target_column}` 为类别型或类别数 <= 20"
        elif is_numeric_series(y):
            task_type = "regression"
            reason = f"目标列 `{target_column}` 为数值型，判定为回归任务"
        else:
            task_type = "unknown"
            reason = "目标变量类型不明确"

        result.data = {
            "task_type": task_type,
            "target_column": target_column,
            "detection_source": "auto",
            "reason": reason,
            "target_unique_count": int(y.nunique(dropna=True)),
            "profile_summary": {
                "n_rows": profile.get("n_rows", len(df)),
                "n_columns": profile.get("n_columns", len(df.columns)),
            },
        }
        return result
