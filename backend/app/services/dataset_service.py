import os
import json
import logging
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.research import Dataset
from app.schemas.research import DatasetCreate, DatasetResponse
from app.core.config import get_settings
from app.skills.data.data_juicer_lite_skill import DataJuicerLiteSkill

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".txt", ".png", ".jpg", ".jpeg", ".tiff", ".wav", ".npy", ".npz"}
TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff"}
TIME_SERIES_EXTENSIONS = {".wav", ".npy", ".npz"}


class DatasetService:
    def __init__(self, db: Session):
        self.db = db

    def _detect_data_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext in TABULAR_EXTENSIONS:
            return "tabular"
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in TIME_SERIES_EXTENSIONS:
            return "time_series"
        if ext == ".json":
            return "json"
        if ext == ".pdf":
            return "pdf"
        return "unknown"

    def _get_storage_dir(self, project_id: str) -> str:
        settings = get_settings()
        base = getattr(settings, "UPLOAD_DIR", "./storage/uploads")
        ds_dir = os.path.join(base, "datasets", project_id)
        os.makedirs(ds_dir, exist_ok=True)
        return ds_dir

    def save_uploaded_file(self, project_id: str, filename: str, content: bytes) -> str:
        ds_dir = self._get_storage_dir(project_id)
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        file_path = os.path.join(ds_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    def analyze_tabular_preview(self, file_path: str, n_preview: int = 10) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "columns": [],
            "dtypes": {},
            "n_rows": 0,
            "n_columns": 0,
            "missing_count": 0,
            "missing_rate": 0.0,
            "statistics": {},
            "preview": [],
        }
        try:
            import pandas as pd
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
            elif ext == ".json":
                df = pd.read_json(file_path)
            elif ext == ".jsonl":
                df = pd.read_json(file_path, lines=True)
            else:
                df = pd.read_csv(file_path)

            result["columns"] = list(df.columns)
            result["dtypes"] = {c: str(dt) for c, dt in df.dtypes.to_dict().items()}
            result["n_rows"] = int(len(df))
            result["n_columns"] = int(len(df.columns))
            total_cells = result["n_rows"] * max(result["n_columns"], 1)
            missing_cells = int(df.isnull().sum().sum())
            result["missing_count"] = missing_cells
            result["missing_rate"] = round(missing_cells / total_cells, 4) if total_cells > 0 else 0.0

            stats = {}
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    stats[col] = {
                        "mean": round(float(df[col].mean()), 4) if not df[col].isnull().all() else None,
                        "std": round(float(df[col].std()), 4) if not df[col].isnull().all() else None,
                        "min": float(df[col].min()) if not df[col].isnull().all() else None,
                        "max": float(df[col].max()) if not df[col].isnull().all() else None,
                        "missing": int(df[col].isnull().sum()),
                    }
                elif pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
                    top_vals = df[col].value_counts().head(5).to_dict()
                    stats[col] = {
                        "unique": int(df[col].nunique()),
                        "top_values": {str(k): int(v) for k, v in top_vals.items()},
                        "missing": int(df[col].isnull().sum()),
                    }
            result["statistics"] = stats
            result["preview"] = json.loads(df.head(n_preview).to_json(orient="records", force_ascii=False))
        except Exception as e:
            logger.warning(f"分析表格数据失败: {e}")
        return result

    def create_dataset(
        self,
        project_id: str,
        filename: str,
        file_path: str,
        file_size: Optional[int] = None,
        auto_analyze: bool = True,
    ) -> Dataset:
        data_type = self._detect_data_type(filename)
        ds = Dataset(
            project_id=project_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            data_type=data_type,
            source_type="upload",
            preprocessing_status="pending",
        )

        if auto_analyze and data_type == "tabular":
            analysis = self.analyze_tabular_preview(file_path)
            ds.n_rows = analysis.get("n_rows") or 0
            ds.n_columns = analysis.get("n_columns") or 0
            ds.columns_json = json.dumps(analysis.get("columns", []), ensure_ascii=False)
            ds.dtypes_json = json.dumps(analysis.get("dtypes", {}), ensure_ascii=False)
            ds.missing_count = analysis.get("missing_count", 0)
            ds.missing_rate = analysis.get("missing_rate", 0.0)
            ds.statistics_json = json.dumps(analysis.get("statistics", {}), ensure_ascii=False)
            ds.preview_json = json.dumps(analysis.get("preview", []), ensure_ascii=False)
            ds.preprocessing_status = "completed"

        self.db.add(ds)
        self.db.commit()
        self.db.refresh(ds)
        return ds

    def get_project_datasets(self, project_id: str) -> List[Dataset]:
        return self.db.query(Dataset).filter(
            Dataset.project_id == project_id
        ).order_by(Dataset.created_at.desc()).all()

    def get_dataset_by_id(self, dataset_id: str) -> Optional[Dataset]:
        return self.db.query(Dataset).filter(Dataset.id == dataset_id).first()

    def run_preprocessing(self, dataset_id: str) -> Optional[Dataset]:
        ds = self.get_dataset_by_id(dataset_id)
        if not ds:
            return None
        ds.preprocessing_status = "processing"
        self.db.flush()

        try:
            if ds.data_type == "tabular":
                analysis = self.analyze_tabular_preview(ds.file_path)
                ds.n_rows = analysis.get("n_rows") or ds.n_rows
                ds.n_columns = analysis.get("n_columns") or ds.n_columns
                ds.columns_json = json.dumps(analysis.get("columns", []), ensure_ascii=False)
                ds.dtypes_json = json.dumps(analysis.get("dtypes", {}), ensure_ascii=False)
                ds.missing_count = analysis.get("missing_count", 0)
                ds.missing_rate = analysis.get("missing_rate", 0.0)
                ds.statistics_json = json.dumps(analysis.get("statistics", {}), ensure_ascii=False)
                ds.preview_json = json.dumps(analysis.get("preview", []), ensure_ascii=False)
            ds.preprocessing_status = "completed"
        except Exception as e:
            logger.error(f"预处理数据集 {dataset_id} 失败: {e}")
            ds.preprocessing_status = "failed"

        self.db.commit()
        self.db.refresh(ds)
        return ds

    def run_quality_analysis(self, project_id: str) -> Dict[str, Any]:
        datasets = self.get_project_datasets(project_id)
        if not datasets:
            return {
                "success": True,
                "data": {
                    "quality_report": {"overall_score": 0.0, "file_count": 0},
                    "file_reports": [],
                    "overall_score": 0.0,
                    "recommendations": ["当前项目无数据文件"],
                    "cleaned_file_paths": [],
                },
                "warnings": ["当前项目无数据文件可供分析"],
            }

        file_metas = []
        for ds in datasets:
            meta = {
                "file_path": ds.file_path,
                "filename": ds.filename,
                "data_type": ds.data_type,
                "n_rows": ds.n_rows or 0,
                "n_columns": ds.n_columns or 0,
                "columns": json.loads(ds.columns_json) if ds.columns_json else [],
                "dtypes": json.loads(ds.dtypes_json) if ds.dtypes_json else {},
                "missing_count": ds.missing_count or 0,
                "statistics": json.loads(ds.statistics_json) if ds.statistics_json else {},
                "preview": json.loads(ds.preview_json) if ds.preview_json else [],
            }
            file_metas.append(meta)

        async def _run():
            try:
                skill = DataJuicerLiteSkill()
                result = await skill.run(
                    input_data={
                        "file_metas": file_metas,
                        "missing_strategy": "report",
                        "outlier_method": "iqr",
                    },
                    context={"stage": "dataset_preprocessing"},
                )
                return {
                    "success": result.success,
                    "data": result.data,
                    "warnings": result.warnings,
                    "errors": result.errors,
                }
            except Exception as e:
                logger.warning(f"DataJuicerLiteSkill 失败: {e}")
                return {"success": False, "error": str(e)}

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"质量分析异常: {e}")
            return {"success": False, "error": str(e)}

    def toggle_hypothesis_use(self, dataset_id: str) -> Optional[Dataset]:
        ds = self.get_dataset_by_id(dataset_id)
        if not ds:
            return None
        ds.use_for_hypothesis = not ds.use_for_hypothesis
        self.db.commit()
        self.db.refresh(ds)
        return ds

    def delete_dataset(self, dataset_id: str) -> bool:
        ds = self.get_dataset_by_id(dataset_id)
        if not ds:
            return False
        try:
            if os.path.exists(ds.file_path):
                os.remove(ds.file_path)
        except Exception:
            pass
        self.db.delete(ds)
        self.db.commit()
        return True

    def to_response(self, ds: Dataset) -> dict:
        return {
            "id": ds.id,
            "project_id": ds.project_id,
            "filename": ds.filename,
            "file_path": ds.file_path,
            "file_size": ds.file_size,
            "data_type": ds.data_type,
            "source_type": ds.source_type,
            "n_rows": ds.n_rows,
            "n_columns": ds.n_columns,
            "columns_json": ds.columns_json,
            "dtypes_json": ds.dtypes_json,
            "missing_count": ds.missing_count,
            "missing_rate": ds.missing_rate,
            "statistics_json": ds.statistics_json,
            "preview_json": ds.preview_json,
            "preprocessing_status": ds.preprocessing_status,
            "use_for_hypothesis": ds.use_for_hypothesis,
            "extra_metadata": ds.extra_metadata,
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
            "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
        }