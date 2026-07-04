"""多源科学数据建模预测与结果自校正服务"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.research import Dataset
from app.skills.modeling import (
    BaselineTrainingSkill,
    DataCleaningPlanSkill,
    DataPreprocessingSkill,
    DatasetProfilingSkill,
    ErrorAnalysisSkill,
    ExperimentTrackingSkill,
    FeatureEngineeringSkill,
    ModelEvaluationSkill,
    SelfCorrectionSkill,
    TaskTypeDetectionSkill,
)
from app.skills.modeling._utils import infer_target_candidates

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class ModelingService:
    def __init__(self, db: Session):
        self.db = db

    def _result_path(self, project_id: str, dataset_id: str) -> str:
        base = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "modeling",
            project_id,
        )
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, f"{dataset_id}.json")

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        return self.db.query(Dataset).filter(Dataset.id == dataset_id).first()

    def load_result(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        ds = self.get_dataset(dataset_id)
        if not ds:
            return None
        path = self._result_path(ds.project_id, dataset_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_project_modeling_results(self, project_id: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        datasets = (
            self.db.query(Dataset)
            .filter(Dataset.project_id == project_id, Dataset.data_type == "tabular")
            .all()
        )
        for ds in datasets:
            data = self.load_result(ds.id)
            if data and data.get("success"):
                results.append(data)
        return results

    def save_result(self, project_id: str, dataset_id: str, payload: Dict[str, Any]) -> str:
        path = self._result_path(project_id, dataset_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        return path

    async def run_modeling_pipeline(
        self,
        dataset_id: str,
        target_column: Optional[str] = None,
        task_type: Optional[str] = None,
        research_task: Optional[str] = None,
    ) -> Dict[str, Any]:
        ds = self.get_dataset(dataset_id)
        if not ds:
            return {"success": False, "error": "数据集不存在"}

        if ds.data_type != "tabular":
            return {"success": False, "error": "仅支持表格型 CSV/Excel 数据集建模"}

        file_path = ds.file_path
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": "数据文件不存在"}

        profile_skill = DatasetProfilingSkill()
        profile_result = await profile_skill.run(
            {"dataset_id": dataset_id, "csv_path": file_path},
            {"stage": "modeling"},
        )
        if not profile_result.success:
            return {"success": False, "error": "; ".join(profile_result.errors)}

        profile = profile_result.data

        clean_skill = DataCleaningPlanSkill()
        clean_result = await clean_skill.run({"profile": profile}, {"stage": "modeling"})

        resolved_target = target_column or self._resolve_target_column(profile, ds)
        if not resolved_target:
            return {
                "success": False,
                "error": "请指定 target_column，或确保数据集中存在可识别目标列",
                "profile": profile,
            }

        task_skill = TaskTypeDetectionSkill()
        task_result = await task_skill.run(
            {
                "target_column": resolved_target,
                "task_type": task_type,
                "profile": profile,
                "csv_path": file_path,
            },
            {"stage": "modeling"},
        )
        if not task_result.success:
            return {"success": False, "error": "; ".join(task_result.errors), "profile": profile}

        detected_task = task_result.data.get("task_type", "unknown")
        effective_task = detected_task if detected_task != "unknown" else "classification"

        feat_skill = FeatureEngineeringSkill()
        feat_result = await feat_skill.run(
            {"profile": profile, "task_type": effective_task, "target_column": resolved_target},
            {"stage": "modeling"},
        )

        preprocess_skill = DataPreprocessingSkill()
        preprocess_result = await preprocess_skill.run(
            {
                "csv_path": file_path,
                "target_column": resolved_target,
                "task_type": effective_task,
            },
            {"stage": "modeling"},
        )
        if not preprocess_result.success:
            return {
                "success": False,
                "error": "; ".join(preprocess_result.errors),
                "profile": profile,
                "task_type": detected_task,
                "target_column": resolved_target,
            }

        train_skill = BaselineTrainingSkill()
        train_result = await train_skill.run(
            {
                "task_type": effective_task,
                "preprocess_artifacts": preprocess_result.data.get("artifacts", {}),
            },
            {"stage": "modeling"},
        )
        if not train_result.success:
            return {
                "success": False,
                "error": "; ".join(train_result.errors),
                "profile": profile,
                "task_type": detected_task,
                "target_column": resolved_target,
            }

        eval_skill = ModelEvaluationSkill()
        eval_result = await eval_skill.run(
            {
                "task_type": train_result.data.get("task_type", effective_task),
                "models": train_result.data.get("models", []),
                "dataset_id": dataset_id,
            },
            {"stage": "modeling"},
        )
        if not eval_result.success:
            return {
                "success": False,
                "error": "; ".join(eval_result.errors),
                "profile": profile,
                "task_type": detected_task,
                "target_column": resolved_target,
            }

        error_skill = ErrorAnalysisSkill()
        error_result = await error_skill.run(
            {"evaluation": eval_result.data},
            {"stage": "modeling"},
        )

        correction_skill = SelfCorrectionSkill()
        correction_result = await correction_skill.run(
            {
                "profile": profile,
                "evaluation": eval_result.data,
                "task_type": train_result.data.get("task_type", effective_task),
                "target_column": resolved_target,
            },
            {"stage": "modeling"},
        )

        payload = {
            "success": True,
            "dataset_id": dataset_id,
            "project_id": ds.project_id,
            "research_task": research_task or "",
            "task_type": train_result.data.get("task_type", effective_task),
            "target_column": resolved_target,
            "profile": profile,
            "preprocessing": {
                k: v for k, v in preprocess_result.data.items() if k != "artifacts"
            },
            "models": eval_result.data.get("models", []),
            "best_model": eval_result.data.get("best_model", ""),
            "charts": eval_result.data.get("charts", []),
            "self_correction_suggestions": correction_result.data.get(
                "self_correction_suggestions", []
            ),
            "cleaning_plan": clean_result.data.get("cleaning_plan", []),
            "feature_plan": feat_result.data.get("feature_plan", {}),
            "error_analysis": error_result.data,
            "is_pilot_validation": correction_result.data.get("is_pilot_validation", False),
            "warnings": (
                profile_result.warnings
                + task_result.warnings
                + preprocess_result.warnings
                + train_result.warnings
                + eval_result.warnings
                + correction_result.warnings
            ),
            "created_at": datetime.now(CHINA_TZ).isoformat(),
        }

        track_skill = ExperimentTrackingSkill()
        await track_skill.run(
            {"project_id": ds.project_id, "dataset_id": dataset_id, "run_payload": payload},
            {"stage": "modeling"},
        )

        self.save_result(ds.project_id, dataset_id, payload)
        self._update_dataset_metadata(ds, payload)
        self.db.commit()
        return payload

    def run_modeling_pipeline_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_modeling_pipeline(**kwargs))

    @staticmethod
    def _resolve_target_column(profile: Dict[str, Any], ds: Dataset) -> Optional[str]:
        candidates = profile.get("target_candidates") or []
        if candidates:
            return candidates[0]

        extra = {}
        if ds.extra_metadata:
            try:
                extra = json.loads(ds.extra_metadata)
            except json.JSONDecodeError:
                extra = {}

        meta_candidates = extra.get("target_candidates") or []
        if isinstance(meta_candidates, dict):
            for cols in meta_candidates.values():
                if cols:
                    return cols[0]
        if isinstance(meta_candidates, list) and meta_candidates:
            return meta_candidates[0]

        columns = profile.get("columns") or []
        inferred = infer_target_candidates(columns)
        return inferred[0] if inferred else None

    @staticmethod
    def _update_dataset_metadata(ds: Dataset, payload: Dict[str, Any]) -> None:
        extra: Dict[str, Any] = {}
        if ds.extra_metadata:
            try:
                extra = json.loads(ds.extra_metadata)
            except json.JSONDecodeError:
                extra = {}
        extra["latest_modeling_result"] = {
            "task_type": payload.get("task_type"),
            "target_column": payload.get("target_column"),
            "best_model": payload.get("best_model"),
            "is_pilot_validation": payload.get("is_pilot_validation"),
            "updated_at": payload.get("created_at"),
        }
        ds.extra_metadata = json.dumps(extra, ensure_ascii=False)
        ds.updated_at = datetime.now(CHINA_TZ)
