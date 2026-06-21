"""数据预处理 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.modeling._utils import (
    load_dataframe,
    sample_dataframe,
    split_feature_target,
)


class DataPreprocessingSkill(BaseSkill):
    name = "DataPreprocessing"
    description = "缺失值填充、编码、标准化与 train/test 划分"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        csv_path = input_data.get("csv_path") or input_data.get("file_path", "")
        target_column = input_data.get("target_column", "")
        task_type = input_data.get("task_type", "classification")

        try:
            df = load_dataframe(csv_path)
            df, sampled = sample_dataframe(df)
            X, y = split_feature_target(df, target_column)
        except Exception as exc:
            result.add_error(str(exc))
            return result

        if X.empty or len(X.columns) == 0:
            result.add_error("除目标列外没有可用特征列")
            return result

        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        import pandas as pd

        numeric_cols: List[str] = [
            col for col in X.columns if pd.api.types.is_numeric_dtype(X[col])
        ]
        categorical_cols: List[str] = [
            col for col in X.columns if col not in numeric_cols
        ]

        transformers = []
        if numeric_cols:
            transformers.append(
                (
                    "num",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]),
                    numeric_cols,
                )
            )
        if categorical_cols:
            transformers.append(
                (
                    "cat",
                    Pipeline([
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]),
                    categorical_cols,
                )
            )

        preprocessor = ColumnTransformer(transformers=transformers)

        stratify = None
        if task_type == "classification":
            if y.nunique(dropna=True) >= 2 and y.value_counts().min() >= 2:
                stratify = y

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=0.2,
                random_state=42,
                stratify=stratify,
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        result.data = {
            "preprocessor_config": {
                "numeric_columns": numeric_cols,
                "categorical_columns": categorical_cols,
                "numeric_imputer": "median",
                "categorical_imputer": "most_frequent",
                "encoder": "OneHotEncoder",
                "scaler": "StandardScaler",
                "train_test_split": "80/20",
            },
            "sampled_for_training": sampled,
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "feature_columns": list(X.columns),
            "artifacts": {
                "X_train": X_train,
                "X_test": X_test,
                "y_train": y_train,
                "y_test": y_test,
                "preprocessor": preprocessor,
            },
        }
        return result
