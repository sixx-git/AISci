"""模型评估 Skill"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.modeling._utils import figure_to_chart_entry, safe_float

logger = logging.getLogger(__name__)


class ModelEvaluationSkill(BaseSkill):
    name = "ModelEvaluation"
    description = "输出分类/回归评估指标、混淆矩阵与图表"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        task_type = input_data.get("task_type", "classification")
        raw_models: List[Dict[str, Any]] = input_data.get("models", [])
        dataset_id = input_data.get("dataset_id", "")

        if not raw_models:
            result.add_error("没有可评估的模型")
            return result

        evaluated: List[Dict[str, Any]] = []
        charts: List[Dict[str, Any]] = []

        for item in raw_models:
            model_name = item.get("model_name", "unknown")
            y_test = item.get("y_test")
            y_pred = item.get("y_pred")
            y_proba = item.get("y_proba")
            metrics: Dict[str, Any] = {}

            try:
                if task_type == "classification":
                    from sklearn.metrics import (
                        accuracy_score,
                        confusion_matrix,
                        f1_score,
                        precision_score,
                        recall_score,
                        roc_auc_score,
                    )

                    metrics["accuracy"] = safe_float(accuracy_score(y_test, y_pred))
                    metrics["precision"] = safe_float(
                        precision_score(y_test, y_pred, average="weighted", zero_division=0)
                    )
                    metrics["recall"] = safe_float(
                        recall_score(y_test, y_pred, average="weighted", zero_division=0)
                    )
                    metrics["f1"] = safe_float(
                        f1_score(y_test, y_pred, average="weighted", zero_division=0)
                    )
                    cm = confusion_matrix(y_test, y_pred)
                    metrics["confusion_matrix"] = cm.tolist()

                    if y_proba is not None:
                        try:
                            if len(set(y_test)) == 2:
                                metrics["roc_auc"] = safe_float(
                                    roc_auc_score(y_test, y_proba[:, 1])
                                )
                            else:
                                metrics["roc_auc"] = safe_float(
                                    roc_auc_score(y_test, y_proba, multi_class="ovr", average="weighted")
                                )
                        except Exception:
                            metrics["roc_auc"] = None

                    chart = self._plot_confusion_matrix(model_name, cm)
                    if chart:
                        charts.append(chart)
                else:
                    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
                    import numpy as np

                    metrics["rmse"] = safe_float(np.sqrt(mean_squared_error(y_test, y_pred)))
                    metrics["mae"] = safe_float(mean_absolute_error(y_test, y_pred))
                    metrics["r2"] = safe_float(r2_score(y_test, y_pred))

                    chart = self._plot_regression_scatter(model_name, y_test, y_pred)
                    if chart:
                        charts.append(chart)
            except Exception as exc:
                logger.warning(f"评估 {model_name} 失败: {exc}")
                result.add_warning(f"{model_name} 评估失败: {exc}")
                continue

            evaluated.append(
                {
                    "model_name": model_name,
                    "metrics": metrics,
                    "feature_importance": item.get("feature_importance", []),
                }
            )

        if not evaluated:
            result.add_error("模型评估全部失败")
            return result

        best_model = self._select_best_model(evaluated, task_type)
        best_model_item = next(
            (m for m in evaluated if m.get("model_name") == best_model),
            evaluated[0],
        )
        if best_model_item.get("feature_importance"):
            fi_chart = self._plot_feature_importance(best_model_item)
            if fi_chart:
                charts.append(fi_chart)

        result.data = {
            "task_type": task_type,
            "models": evaluated,
            "best_model": best_model,
            "charts": charts,
            "dataset_id": dataset_id,
        }
        return result

    @staticmethod
    def _select_best_model(models: List[Dict[str, Any]], task_type: str) -> str:
        if task_type == "classification":
            key = "f1"
            fallback = "accuracy"
        else:
            key = "r2"
            fallback = "rmse"

        def score(item: Dict[str, Any]) -> float:
            metrics = item.get("metrics", {})
            primary = metrics.get(key)
            if primary is not None:
                return float(primary)
            secondary = metrics.get(fallback)
            if secondary is None:
                return float("-inf") if task_type == "classification" else float("-inf")
            if key == "r2":
                return float(secondary)
            if fallback == "rmse":
                return -float(secondary)
            return float(secondary)

        best = max(models, key=score)
        return best.get("model_name", "")

    @staticmethod
    def _plot_confusion_matrix(model_name: str, cm):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(5, 4))
            im = ax.imshow(cm, cmap="Blues")
            ax.set_title(f"{model_name} Confusion Matrix")
            ax.set_xlabel("Predicted")
            ax.set_ylabel("True")
            fig.colorbar(im, ax=ax)
            return figure_to_chart_entry(
                f"{model_name} 混淆矩阵",
                "confusion_matrix",
                fig,
                f"cm_{model_name}",
            )
        except Exception:
            return None
        finally:
            try:
                plt.close(fig)
            except Exception:
                pass

    @staticmethod
    def _plot_regression_scatter(model_name: str, y_test, y_pred):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(5, 4))
            ax.scatter(y_test, y_pred, alpha=0.6)
            ax.set_title(f"{model_name} Actual vs Predicted")
            ax.set_xlabel("Actual")
            ax.set_ylabel("Predicted")
            return figure_to_chart_entry(
                f"{model_name} 预测散点图",
                "scatter",
                fig,
                f"scatter_{model_name}",
            )
        except Exception:
            return None
        finally:
            try:
                plt.close(fig)
            except Exception:
                pass

    @staticmethod
    def _plot_feature_importance(best_model_item: Dict[str, Any]):
        fi = best_model_item.get("feature_importance") or []
        if not fi:
            return None
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            names = [x["feature"] for x in fi[:8]]
            values = [x["importance"] for x in fi[:8]]
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.barh(names[::-1], values[::-1])
            ax.set_title(f"{best_model_item.get('model_name', '')} Feature Importance")
            return figure_to_chart_entry(
                "特征重要性",
                "feature_importance",
                fig,
                "feature_importance",
            )
        except Exception:
            return None
        finally:
            try:
                plt.close(fig)
            except Exception:
                pass
