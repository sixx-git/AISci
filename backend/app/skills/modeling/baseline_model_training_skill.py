"""基线模型训练 Skill"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class BaselineModelTrainingSkill(BaseSkill):
    name = "BaselineModelTraining"
    description = "训练分类/回归基线模型"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        task_type = input_data.get("task_type", "unknown")
        artifacts = input_data.get("preprocess_artifacts", {})

        X_train = artifacts.get("X_train")
        X_test = artifacts.get("X_test")
        y_train = artifacts.get("y_train")
        y_test = artifacts.get("y_test")
        preprocessor = artifacts.get("preprocessor")

        if any(v is None for v in [X_train, X_test, y_train, y_test, preprocessor]):
            result.add_error("缺少预处理产物，无法训练模型")
            return result

        if task_type == "time_series":
            result.add_warning("time_series 任务暂以回归基线近似验证，建议后续引入时序模型")
            task_type = "regression"
        if task_type == "unknown":
            result.add_warning("任务类型未知，默认尝试分类与回归两套基线")
            task_type = "classification"

        try:
            X_train_t = preprocessor.fit_transform(X_train)
            X_test_t = preprocessor.transform(X_test)
        except Exception as exc:
            result.add_error(f"特征预处理失败: {exc}")
            return result

        trained: List[Dict[str, Any]] = []

        if task_type == "classification":
            from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
            from sklearn.linear_model import LogisticRegression

            model_defs = [
                ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=42)),
                ("RandomForestClassifier", RandomForestClassifier(n_estimators=100, random_state=42)),
                ("GradientBoostingClassifier", GradientBoostingClassifier(random_state=42)),
            ]
        else:
            from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
            from sklearn.linear_model import LinearRegression

            model_defs = [
                ("LinearRegression", LinearRegression()),
                ("RandomForestRegressor", RandomForestRegressor(n_estimators=100, random_state=42)),
                ("GradientBoostingRegressor", GradientBoostingRegressor(random_state=42)),
            ]

        for model_name, estimator in model_defs:
            try:
                estimator.fit(X_train_t, y_train)
                y_pred = estimator.predict(X_test_t)
                y_proba = None
                if hasattr(estimator, "predict_proba") and task_type == "classification":
                    try:
                        y_proba = estimator.predict_proba(X_test_t)
                    except Exception:
                        y_proba = None

                feature_importance = []
                if hasattr(estimator, "feature_importances_"):
                    import numpy as np

                    importances = estimator.feature_importances_
                    top_idx = np.argsort(importances)[::-1][:10]
                    feature_importance = [
                        {"feature": f"feature_{i}", "importance": round(float(importances[i]), 6)}
                        for i in top_idx
                    ]

                trained.append(
                    {
                        "model_name": model_name,
                        "task_type": task_type,
                        "y_test": y_test,
                        "y_pred": y_pred,
                        "y_proba": y_proba,
                        "feature_importance": feature_importance,
                    }
                )
            except Exception as exc:
                logger.warning(f"模型 {model_name} 训练失败: {exc}")
                result.add_warning(f"{model_name} 训练失败: {exc}")

        if not trained:
            result.add_error("所有基线模型训练失败")
            return result

        result.data = {
            "task_type": task_type,
            "models": trained,
            "n_models_trained": len(trained),
        }
        return result
