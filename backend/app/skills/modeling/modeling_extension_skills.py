"""建模扩展 Skill — 清洗计划、特征工程、错误分析、实验追踪、基线训练别名"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.modeling.baseline_model_training_skill import BaselineModelTrainingSkill
from app.skills.modeling.model_evaluation_skill import ModelEvaluationSkill

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class BaselineTrainingSkill(BaseSkill):
    """BaselineModelTraining 别名，并尝试 XGBoost / LightGBM / CatBoost / MLP。"""

    name = "BaselineTraining"
    description = "自动训练 RF/XGBoost/LightGBM/CatBoost/MLP 等基线模型"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        inner = BaselineModelTrainingSkill()
        result = await inner.run(input_data, context)
        if not result.success:
            return result

        task_type = result.data.get("task_type", input_data.get("task_type", "classification"))
        artifacts = input_data.get("preprocess_artifacts", {})
        X_train, y_train = artifacts.get("X_train"), artifacts.get("y_train")
        X_test, y_test = artifacts.get("X_test"), artifacts.get("y_test")
        preprocessor = artifacts.get("preprocessor")
        if any(v is None for v in (X_train, X_test, y_train, y_test, preprocessor)):
            return result

        try:
            X_train_t = preprocessor.transform(X_train)
            X_test_t = preprocessor.transform(X_test)
        except Exception:
            return result

        extra_models = self._optional_boosters(task_type)
        for model_name, estimator in extra_models:
            try:
                estimator.fit(X_train_t, y_train)
                y_pred = estimator.predict(X_test_t)
                y_proba = None
                if hasattr(estimator, "predict_proba") and task_type == "classification":
                    try:
                        y_proba = estimator.predict_proba(X_test_t)
                    except Exception:
                        pass
                result.data.setdefault("models", []).append({
                    "model_name": model_name,
                    "y_test": y_test,
                    "y_pred": y_pred,
                    "y_proba": y_proba,
                    "feature_importance": [],
                })
            except Exception as exc:
                result.add_warning(f"{model_name} 训练跳过: {exc}")
        return result

    @staticmethod
    def _optional_boosters(task_type: str) -> List[tuple]:
        models: List[tuple] = []
        if task_type == "classification":
            try:
                from xgboost import XGBClassifier
                models.append(("XGBClassifier", XGBClassifier(n_estimators=100, random_state=42, verbosity=0)))
            except ImportError:
                pass
            try:
                from lightgbm import LGBMClassifier
                models.append(("LGBMClassifier", LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)))
            except ImportError:
                pass
            try:
                from catboost import CatBoostClassifier
                models.append(("CatBoostClassifier", CatBoostClassifier(iterations=100, random_seed=42, verbose=0)))
            except ImportError:
                pass
            try:
                from sklearn.neural_network import MLPClassifier
                models.append(("MLPClassifier", MLPClassifier(max_iter=300, random_state=42)))
            except ImportError:
                pass
        else:
            try:
                from xgboost import XGBRegressor
                models.append(("XGBRegressor", XGBRegressor(n_estimators=100, random_state=42, verbosity=0)))
            except ImportError:
                pass
            try:
                from lightgbm import LGBMRegressor
                models.append(("LGBMRegressor", LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)))
            except ImportError:
                pass
            try:
                from catboost import CatBoostRegressor
                models.append(("CatBoostRegressor", CatBoostRegressor(iterations=100, random_seed=42, verbose=0)))
            except ImportError:
                pass
            try:
                from sklearn.neural_network import MLPRegressor
                models.append(("MLPRegressor", MLPRegressor(max_iter=300, random_state=42)))
            except ImportError:
                pass
        return models


class DataCleaningPlanSkill(BaseSkill):
    name = "DataCleaningPlan"
    description = "根据数据质量概览自动生成清洗计划"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        profile = input_data.get("profile") or {}
        steps: List[Dict[str, str]] = []

        missing_rate = float(profile.get("missing_rate") or 0)
        if missing_rate > 0.05:
            steps.append({
                "step": "missing_value_treatment",
                "action": "数值列中位数/类别列众数插补；缺失率>50%列考虑删除",
                "priority": "high" if missing_rate > 0.2 else "medium",
            })

        for hint in profile.get("outlier_hints") or []:
            steps.append({"step": "outlier_handling", "action": hint, "priority": "medium"})

        for col, stats in (profile.get("numeric_stats") or {}).items():
            if stats.get("missing_rate", 0) > 0.3:
                steps.append({
                    "step": "drop_or_impute",
                    "action": f"列 `{col}` 缺失率 {stats['missing_rate']:.1%}，建议删除或专门插补",
                    "priority": "high",
                })

        for col, dist in (profile.get("categorical_distribution") or {}).items():
            if dist.get("unique", 0) > 50:
                steps.append({
                    "step": "high_cardinality",
                    "action": f"列 `{col}` 高基数类别 ({dist['unique']})，建议 target/frequency 编码",
                    "priority": "medium",
                })

        if not steps:
            steps.append({"step": "baseline_clean", "action": "数据质量良好，执行标准缺失插补与类型校验", "priority": "low"})

        result.data = {"cleaning_plan": steps, "step_count": len(steps)}
        return result


class FeatureEngineeringSkill(BaseSkill):
    name = "FeatureEngineering"
    description = "特征选择、标准化、类别编码、时间序列窗口建议"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        profile = input_data.get("profile") or {}
        task_type = input_data.get("task_type", "classification")
        target = input_data.get("target_column", "")

        numeric_cols = list((profile.get("numeric_stats") or {}).keys())
        cat_cols = list((profile.get("categorical_distribution") or {}).keys())
        if target in numeric_cols:
            numeric_cols.remove(target)
        if target in cat_cols:
            cat_cols.remove(target)

        plan = {
            "scaling": {"method": "StandardScaler", "columns": numeric_cols},
            "encoding": {"method": "OneHotEncoder", "columns": cat_cols},
            "feature_selection": {
                "method": "model_importance_or_correlation",
                "max_features": min(30, len(numeric_cols) + len(cat_cols)),
            },
        }
        if task_type == "time_series":
            plan["time_series_windows"] = {
                "suggested_windows": [3, 7, 14, 30],
                "note": "对时序列构造 lag/rolling 特征",
            }

        result.data = {"feature_plan": plan, "numeric_count": len(numeric_cols), "categorical_count": len(cat_cols)}
        return result


class ErrorAnalysisSkill(BaseSkill):
    name = "ErrorAnalysis"
    description = "错误样本聚类、特征贡献、混淆矩阵分析"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        evaluation = input_data.get("evaluation") or {}
        models = evaluation.get("models") or []
        if not models:
            result.add_warning("无可分析模型")
            result.data = {"error_clusters": [], "confusion_analysis": {}, "feature_contributions": []}
            return result

        best_name = evaluation.get("best_model") or models[0].get("model_name")
        best = next((m for m in models if m.get("model_name") == best_name), models[0])
        metrics = best.get("metrics", {})
        cm = metrics.get("confusion_matrix")

        confusion_analysis: Dict[str, Any] = {}
        if cm:
            confusion_analysis = {
                "matrix": cm,
                "dominant_errors": "检查非对角线高值单元格对应类别",
            }

        feature_contributions = best.get("feature_importance") or []
        error_clusters = []
        y_test, y_pred = best.get("y_test"), best.get("y_pred")
        if y_test is not None and y_pred is not None:
            try:
                import numpy as np
                y_test_a = np.asarray(y_test)
                y_pred_a = np.asarray(y_pred)
                wrong_idx = np.where(y_test_a != y_pred_a)[0]
                error_clusters.append({
                    "cluster_id": "misclassified",
                    "count": int(len(wrong_idx)),
                    "sample_indices": wrong_idx[:20].tolist(),
                })
            except Exception as exc:
                result.add_warning(f"错误样本分析跳过: {exc}")

        result.data = {
            "best_model": best_name,
            "confusion_analysis": confusion_analysis,
            "feature_contributions": feature_contributions[:15],
            "error_clusters": error_clusters,
        }
        return result


class ExperimentTrackingSkill(BaseSkill):
    name = "ExperimentTracking"
    description = "记录每次训练参数和指标"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        project_id = input_data.get("project_id", "")
        dataset_id = input_data.get("dataset_id", "")
        run_payload = input_data.get("run_payload") or {}

        entry = {
            "run_id": f"run_{datetime.now(CHINA_TZ).strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now(CHINA_TZ).isoformat(),
            "project_id": project_id,
            "dataset_id": dataset_id,
            "task_type": run_payload.get("task_type"),
            "target_column": run_payload.get("target_column"),
            "best_model": run_payload.get("best_model"),
            "models": [
                {"name": m.get("model_name"), "metrics": m.get("metrics")}
                for m in (run_payload.get("models") or [])
            ],
            "hyperparameters_note": run_payload.get("preprocessing", {}),
        }

        if project_id and dataset_id:
            base = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "storage", "experiment_tracking", project_id,
            )
            os.makedirs(base, exist_ok=True)
            log_path = os.path.join(base, f"{dataset_id}_runs.jsonl")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            entry["log_path"] = log_path

        result.data = {"tracking_entry": entry, "logged": bool(project_id)}
        return result
