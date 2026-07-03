import os
import json
import logging
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.project_modes import ProjectMode, normalize_project_mode
from app.models.research import Dataset
from app.schemas.research import DatasetCreate, DatasetResponse
from app.core.config import get_settings
from app.skills.data.data_juicer_lite_skill import DataJuicerLiteSkill
from app.skills.data_finder.file_format_registry import (
    CHEMISTRY_EXTENSIONS,
    is_allowed_upload_filename,
    is_chemistry_format,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".txt", ".md",
                        ".png", ".jpg", ".jpeg", ".tiff", ".webp", ".gif",
                        ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac",
                        ".npy", ".npz", ".zip"} | CHEMISTRY_EXTENSIONS
TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff"}
TIME_SERIES_EXTENSIONS = {".wav", ".npy", ".npz"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}
JSON_EXTENSIONS = {".json", ".jsonl"}

TARGET_COLUMN_KEYWORDS = [
    "label", "target", "class", "y", "accuracy", "score", "result", "outcome",
    "行为", "类别", "标签", "准确率", "评分", "目标", "结果", "分类",
    "diagnosis", "prognosis", "response", "status", "flag",
    "label_col", "target_col", "outcome_col",
]


class DatasetService:
    def __init__(self, db: Session):
        self.db = db

    def _detect_data_type(self, filename: str) -> str:
        if is_chemistry_format(filename):
            return "chem_structure"
        ext = os.path.splitext(filename)[1].lower()
        if ext in TABULAR_EXTENSIONS:
            return "tabular"
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in TIME_SERIES_EXTENSIONS:
            return "time_series"
        if ext in AUDIO_EXTENSIONS:
            return "time_series"
        if ext in JSON_EXTENSIONS:
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

    def _analyze_image_file(self, file_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "image_count": 1,
            "width": 0,
            "height": 0,
            "channels": 0,
            "format": "",
            "file_size_bytes": 0,
        }
        try:
            result["file_size_bytes"] = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            result["format"] = ext.lstrip(".")
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    result["width"], result["height"] = img.size
                    mode = img.mode
                    if mode == "RGB":
                        result["channels"] = 3
                    elif mode == "RGBA":
                        result["channels"] = 4
                    elif mode == "L":
                        result["channels"] = 1
                    else:
                        result["channels"] = len(mode) if mode else 0
            except ImportError:
                result["_pillow_warning"] = "Pillow 不可用，无法获取图像详细信息"
        except Exception as e:
            logger.warning(f"分析图像文件失败: {e}")
            result["_error"] = str(e)
        return result

    def _analyze_timeseries_file(self, file_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "file_format": "",
            "n_samples": 0,
            "shape": [],
            "duration_estimate": "",
            "file_size_bytes": 0,
        }
        try:
            result["file_size_bytes"] = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            result["file_format"] = ext.lstrip(".")
            if ext in (".npy", ".npz"):
                try:
                    import numpy as np
                    if ext == ".npy":
                        arr = np.load(file_path, allow_pickle=True)
                        result["shape"] = list(arr.shape) if hasattr(arr, "shape") else []
                        result["n_samples"] = arr.shape[0] if hasattr(arr, "shape") and len(arr.shape) > 0 else 0
                    else:
                        data = np.load(file_path, allow_pickle=True)
                        keys = list(data.keys()) if hasattr(data, "files") else []
                        result["shape"] = [f"{k}: {list(data[k].shape) if hasattr(data[k], 'shape') else '?'}" for k in keys[:5]]
                        result["n_samples"] = len(keys)
                except ImportError:
                    result["_numpy_warning"] = "NumPy 不可用"
            elif ext == ".wav":
                try:
                    import wave
                    with wave.open(file_path, "rb") as wf:
                        result["n_channels"] = wf.getnchannels()
                        result["sample_width"] = wf.getsampwidth()
                        result["frame_rate"] = wf.getframerate()
                        result["n_frames"] = wf.getnframes()
                        result["n_samples"] = result["n_frames"]
                        result["duration_estimate"] = f"{result['n_frames'] / max(result['frame_rate'], 1):.2f}s"
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"分析时间序列文件失败: {e}")
            result["_error"] = str(e)
        return result

    def _analyze_json_file(self, file_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "file_size_bytes": 0,
            "record_count": 0,
            "is_array": False,
            "top_level_keys": [],
            "field_candidates": [],
            "preview": [],
        }
        try:
            result["file_size_bytes"] = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            with open(file_path, "r", encoding="utf-8") as f:
                if ext == ".jsonl":
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 10:
                            break
                        if line.strip():
                            lines.append(json.loads(line))
                    result["record_count"] = sum(1 for _ in open(file_path, "r", encoding="utf-8") if _.strip())
                    if lines:
                        result["is_array"] = False
                        result["top_level_keys"] = sorted(list({k for r in lines for k in r.keys()}))
                        result["field_candidates"] = result["top_level_keys"]
                        result["preview"] = lines[:5]
                else:
                    data = json.load(f)
                    if isinstance(data, list):
                        result["is_array"] = True
                        result["record_count"] = len(data)
                        if data:
                            result["top_level_keys"] = sorted(list({k for r in data[:50] if isinstance(r, dict) for k in r.keys()}))
                            result["field_candidates"] = result["top_level_keys"]
                            result["preview"] = data[:5]
                    elif isinstance(data, dict):
                        result["top_level_keys"] = sorted(list(data.keys()))
                        result["field_candidates"] = result["top_level_keys"]
                        result["preview"] = [{k: str(v)[:80] for k, v in list(data.items())[:10]}]
        except Exception as e:
            logger.warning(f"分析 JSON 文件失败: {e}")
            result["_error"] = str(e)
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

        if auto_analyze:
            try:
                if data_type == "chem_structure":
                    import asyncio
                    from app.skills.data_finder.structured_file_extraction_skill import extract_tables_from_file

                    tables = asyncio.run(extract_tables_from_file(
                        file_path,
                        source_title=filename,
                        output_dir=os.path.dirname(file_path),
                        filename=filename,
                        max_records=10_000,
                    ))
                    if tables:
                        csv_path = tables[0].get("csv_path")
                        if csv_path and os.path.exists(csv_path):
                            analysis = self.analyze_tabular_preview(csv_path)
                            ds.n_rows = analysis.get("n_rows") or tables[0].get("row_count", 0)
                            ds.n_columns = analysis.get("n_columns") or len(tables[0].get("columns", []))
                            ds.columns_json = json.dumps(analysis.get("columns", tables[0].get("columns", [])), ensure_ascii=False)
                            ds.dtypes_json = json.dumps(analysis.get("dtypes", {}), ensure_ascii=False)
                            ds.missing_count = analysis.get("missing_count", 0)
                            ds.missing_rate = analysis.get("missing_rate", 0.0)
                            ds.statistics_json = json.dumps(analysis.get("statistics", {}), ensure_ascii=False)
                            ds.preview_json = json.dumps(analysis.get("preview", []), ensure_ascii=False)
                            ds.extra_metadata = json.dumps({
                                "derived_csv_path": csv_path,
                                "extraction_method": "chem_structure",
                                "source_format": tables[0].get("format"),
                                "truncated": tables[0].get("truncated", False),
                            }, ensure_ascii=False)
                            ds.preprocessing_status = "completed"
                        else:
                            ds.n_rows = int(tables[0].get("row_count") or 0)
                            ds.extra_metadata = json.dumps({"extraction": tables[0]}, ensure_ascii=False)
                            ds.preprocessing_status = "completed"
                    else:
                        ds.preprocessing_status = "failed"
                        ds.extra_metadata = json.dumps({"error": "化学结构文件解析失败"}, ensure_ascii=False)
                elif data_type == "tabular":
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
                elif data_type == "image":
                    analysis = self._analyze_image_file(file_path)
                    ds.extra_metadata = json.dumps(analysis, ensure_ascii=False)
                    ds.preprocessing_status = "completed"
                elif data_type == "time_series":
                    analysis = self._analyze_timeseries_file(file_path)
                    ds.n_rows = analysis.get("n_samples", 0)
                    ds.extra_metadata = json.dumps(analysis, ensure_ascii=False)
                    ds.preprocessing_status = "completed"
                elif data_type in ("json",):
                    analysis = self._analyze_json_file(file_path)
                    ds.n_rows = analysis.get("record_count", 0)
                    ds.extra_metadata = json.dumps(analysis, ensure_ascii=False)
                    ds.preprocessing_status = "completed"
                else:
                    ds.extra_metadata = json.dumps({
                        "file_size_bytes": file_size or 0,
                        "data_type": data_type,
                    }, ensure_ascii=False)
                    ds.preprocessing_status = "completed"
            except Exception as e:
                logger.error(f"创建数据集自动分析失败: {e}")
                ds.extra_metadata = json.dumps({"auto_analyze_error": str(e)}, ensure_ascii=False)
                ds.preprocessing_status = "failed"

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

    @staticmethod
    def _identify_target_candidates(columns: List[str]) -> Dict[str, List[str]]:
        want_keys_doc: Dict[str, str] = {
            "binary_classification": "Binary classification target candidates",
            "multi_classification": "Multiclass classification target candidates",
            "regression": "Regression target candidates",
            "generic_metric": "Generic metric / score candidates",
            "generic_target": "Generic target candidates",
        }
        target_candidates: Dict[str, List[str]] = {k: [] for k in want_keys_doc}
        numeric_candidates: List[str] = []
        categorical_candidates: List[str] = []

        for col in columns:
            col_lower = col.lower().strip()
            matches = []
            for kw in TARGET_COLUMN_KEYWORDS:
                if kw.lower() in col_lower or col_lower == kw.lower():
                    matches.append(kw)
            if not matches:
                continue

            if any(k in col_lower for k in ("label", "class", "category", "类别", "标签", "分类", "diagnosis")):
                if "binary" in col_lower:
                    target_candidates["binary_classification"].append(col)
                else:
                    target_candidates["multi_classification"].append(col)
            elif any(k in col_lower for k in ("accuracy", "score", "result", "outcome", "评分", "准确率", "结果")):
                target_candidates["regression"].append(col)
            else:
                target_candidates["generic_target"].append(col)

        numeric_candidates_dedup = list(dict.fromkeys([
            c for c in target_candidates["regression"]
            + target_candidates["binary_classification"]
            + target_candidates["multi_classification"]
        ]))
        categorical_candidates_dedup = list(dict.fromkeys([
            c for c in target_candidates["binary_classification"]
            + target_candidates["multi_classification"]
        ]))
        generic_metric = list(dict.fromkeys([
            c for c in target_candidates["regression"]
            + target_candidates["generic_target"]
        ]))

        return {
            "target_candidates": {k: v for k, v in target_candidates.items() if v},
            "numeric_field_candidates": numeric_candidates_dedup,
            "categorical_field_candidates": categorical_candidates_dedup,
            "generic_metric_candidates": generic_metric,
        }

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

                columns = analysis.get("columns", [])
                candidates = self._identify_target_candidates(columns)
                existing_meta = {}
                if ds.extra_metadata:
                    try:
                        existing_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                    except json.JSONDecodeError:
                        pass
                existing_meta.update(candidates)
                ds.extra_metadata = json.dumps(existing_meta, ensure_ascii=False)

            elif ds.data_type == "image":
                analysis = self._analyze_image_file(ds.file_path)
                existing_meta = {}
                if ds.extra_metadata:
                    try:
                        existing_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                    except json.JSONDecodeError:
                        pass
                existing_meta.update(analysis)
                ds.extra_metadata = json.dumps(existing_meta, ensure_ascii=False)
            elif ds.data_type == "time_series":
                analysis = self._analyze_timeseries_file(ds.file_path)
                ds.n_rows = analysis.get("n_samples", ds.n_rows)
                existing_meta = {}
                if ds.extra_metadata:
                    try:
                        existing_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                    except json.JSONDecodeError:
                        pass
                existing_meta.update(analysis)
                ds.extra_metadata = json.dumps(existing_meta, ensure_ascii=False)
            elif ds.data_type in ("json",):
                analysis = self._analyze_json_file(ds.file_path)
                ds.n_rows = analysis.get("record_count", ds.n_rows)
                existing_meta = {}
                if ds.extra_metadata:
                    try:
                        existing_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                    except json.JSONDecodeError:
                        pass
                existing_meta.update(analysis)
                ds.extra_metadata = json.dumps(existing_meta, ensure_ascii=False)

            ds.preprocessing_status = "completed"
        except Exception as e:
            logger.error(f"预处理数据集 {dataset_id} 失败: {e}")
            ds.preprocessing_status = "failed"
            error_meta = {}
            if ds.extra_metadata:
                try:
                    error_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                except json.JSONDecodeError:
                    pass
            error_meta["error_message"] = str(e)
            ds.extra_metadata = json.dumps(error_meta, ensure_ascii=False)

        self.db.commit()
        self.db.refresh(ds)
        return ds

    def run_single_quality_analysis(self, dataset_id: str) -> Dict[str, Any]:
        ds = self.get_dataset_by_id(dataset_id)
        if not ds:
            return {
                "success": False,
                "error": f"数据集 {dataset_id} 不存在",
                "data": None,
            }

        file_meta = {
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

        async def _run():
            try:
                skill = DataJuicerLiteSkill()
                result = await skill.run(
                    input_data={
                        "file_metas": [file_meta],
                        "missing_strategy": "report",
                        "outlier_method": "iqr",
                    },
                    context={"stage": "single_dataset_quality"},
                )
                return {
                    "success": result.success,
                    "data": result.data,
                    "warnings": result.warnings,
                    "errors": result.errors,
                }
            except Exception as e:
                logger.warning(f"DataJuicerLiteSkill 单文件失败: {e}")
                return {"success": False, "error": str(e)}

        try:
            quality_result = asyncio.run(_run())
        except Exception as e:
            logger.warning(f"质量分析异常: {e}")
            quality_result = {"success": False, "error": str(e)}

        if quality_result.get("success") and quality_result.get("data"):
            existing_meta = {}
            if ds.extra_metadata:
                try:
                    existing_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                except json.JSONDecodeError:
                    pass
            existing_meta["quality_report"] = quality_result["data"].get("quality_report", {})
            existing_meta["quality_recommendations"] = quality_result["data"].get("recommendations", [])
            ds.extra_metadata = json.dumps(existing_meta, ensure_ascii=False)
            self.db.commit()

        return quality_result

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

    def get_project_data_context(self, project_id: str) -> Dict[str, Any]:
        datasets = self.get_project_datasets(project_id)
        context: Dict[str, Any] = {
            "dataset_count": len(datasets),
            "available_modalities": [],
            "datasets": [],
            "field_candidates": [],
            "target_candidates": [],
            "quality_summary": {},
            "warnings": [],
        }

        if not datasets:
            context["warnings"].append("当前项目缺少实测数据集，假设仅能基于文献和用户问题生成")
            return context

        modalities_set: set = set()
        all_fields: List[str] = []
        all_targets: List[str] = []
        total_quality_scores: List[float] = []
        total_rows = 0
        total_missing = 0
        all_numeric_candidates: List[str] = []
        all_categorical_candidates: List[str] = []

        for ds in datasets:
            ds_entry: Dict[str, Any] = {
                "dataset_id": ds.id,
                "filename": ds.filename,
                "file_path": ds.file_path,
                "data_type": ds.data_type or "unknown",
                "source_type": getattr(ds, "source_type", "upload") or "upload",
                "n_rows": ds.n_rows or 0,
                "n_columns": ds.n_columns or 0,
                "columns": [],
                "dtypes": {},
                "missing_count": ds.missing_count or 0,
                "missing_rate": ds.missing_rate or 0.0,
                "statistics": {},
                "preview": [],
                "use_for_hypothesis": bool(ds.use_for_hypothesis),
                "preprocessing_status": ds.preprocessing_status or "pending",
            }

            if ds.columns_json:
                try:
                    cols = json.loads(ds.columns_json)
                    ds_entry["columns"] = cols
                    all_fields.extend(cols)
                except json.JSONDecodeError:
                    pass
            if ds.dtypes_json:
                try:
                    ds_entry["dtypes"] = json.loads(ds.dtypes_json)
                except json.JSONDecodeError:
                    pass
            if ds.statistics_json:
                try:
                    ds_entry["statistics"] = json.loads(ds.statistics_json)
                except json.JSONDecodeError:
                    pass
            if ds.preview_json:
                try:
                    ds_entry["preview"] = json.loads(ds.preview_json)[:5]
                except json.JSONDecodeError:
                    pass

            modalities_set.add(ds.data_type or "unknown")
            total_rows += ds.n_rows or 0
            total_missing += ds.missing_count or 0

            if ds.extra_metadata:
                try:
                    extra = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                    if isinstance(extra, dict):
                        if extra.get("target_candidates"):
                            tc = extra["target_candidates"]
                            if isinstance(tc, dict):
                                for tc_list in tc.values():
                                    if isinstance(tc_list, list):
                                        all_targets.extend(tc_list)
                            elif isinstance(tc, list):
                                all_targets.extend(tc)
                        if extra.get("numeric_field_candidates"):
                            all_numeric_candidates.extend(extra["numeric_field_candidates"])
                        if extra.get("categorical_field_candidates"):
                            all_categorical_candidates.extend(extra["categorical_field_candidates"])
                        if extra.get("quality_report"):
                            qr = extra["quality_report"]
                            if isinstance(qr, dict) and qr.get("overall_score") is not None:
                                total_quality_scores.append(float(qr["overall_score"]))
                        ds_entry["quality_score"] = extra.get("quality_report", {}).get("overall_score") if isinstance(extra.get("quality_report"), dict) else None
                        ds_entry["quality_recommendations"] = extra.get("quality_recommendations", [])
                        ds_entry["target_candidates"] = extra.get("target_candidates", {})
                except json.JSONDecodeError:
                    pass

            context["datasets"].append(ds_entry)

        context["available_modalities"] = sorted(list(modalities_set))
        context["field_candidates"] = list(dict.fromkeys(all_fields))[:100]
        context["target_candidates"] = list(dict.fromkeys(all_targets))[:30]

        total_cells = total_rows * max(len(all_fields), 1)
        overall_missing_rate = round(total_missing / max(total_cells, 1), 4)

        context["quality_summary"] = {
            "overall_score": round(sum(total_quality_scores) / max(len(total_quality_scores), 1), 3) if total_quality_scores else None,
            "total_rows": total_rows,
            "total_missing": total_missing,
            "missing_rate": overall_missing_rate,
            "dataset_count": len(datasets),
            "numeric_candidates": list(dict.fromkeys(all_numeric_candidates))[:20],
            "categorical_candidates": list(dict.fromkeys(all_categorical_candidates))[:20],
        }

        if not context["datasets"]:
            context["warnings"].append("当前项目缺少可用于假设生成的数据集")

        project_mode = ProjectMode.GENERAL.value
        try:
            from app.models.project import Project

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project_mode = normalize_project_mode(getattr(project, "project_mode", None))
        except Exception:
            pass

        context["project_mode"] = project_mode
        if project_mode == ProjectMode.FEDERATED_LEARNING.value:
            from app.services.federated_experiment_service import get_federated_experiment_service

            fl_service = get_federated_experiment_service(self.db)
            context["fl_context"] = fl_service.build_fl_context_from_data_context(context)
            fl_ctx = context["fl_context"] or {}
            if fl_ctx.get("fl_setting") == "vertical_fl":
                context["warnings"].append(
                    "已识别为 vertical_fl：检测到 party_id/entity_id/feature_owner/label_owner 等 VFL 字段"
                )
            elif not fl_ctx.get("detected_fields"):
                context["warnings"].append(
                    "联邦学习模式：请上传含 party_id/entity_id/feature_owner/label_owner 或 "
                    "method/global_accuracy 等字段的 CSV"
                )

        try:
            from app.services.data_finder_service import get_data_finder_service

            df_results = get_data_finder_service(self.db).load_results(project_id)
            if df_results:
                context["data_finder_results"] = df_results
                merged = df_results.get("merged") or {}
                csv_path = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
                if csv_path:
                    context["data_finder_merged_csv"] = csv_path
                if df_results.get("coverage_report"):
                    context["data_finder_coverage"] = df_results["coverage_report"]
        except Exception:
            pass

        try:
            from app.services.knowledge_graph_service import get_knowledge_graph_service

            kg_ctx = get_knowledge_graph_service(self.db).get_kg_context_for_agents(project_id)
            if kg_ctx:
                context["knowledge_graph"] = kg_ctx
        except Exception:
            pass

        try:
            from app.services.multimodal_service import get_multimodal_service

            mm_ctx = get_multimodal_service(self.db).get_multimodal_context(project_id)
            context["multimodal_evidence"] = mm_ctx.get("multimodal_evidence") or []
            context["multimodal_assets"] = mm_ctx.get("multimodal_assets") or []
            context["multimodal_evidence_count"] = mm_ctx.get("multimodal_evidence_count") or 0
            if mm_ctx.get("modalities_present"):
                context["available_modalities"] = sorted(
                    set(context.get("available_modalities") or []) | set(mm_ctx["modalities_present"])
                )
            if context["multimodal_evidence_count"] == 0 and any(
                a.get("modality") in ("image", "audio") for a in (mm_ctx.get("multimodal_assets") or [])
            ):
                context["warnings"].append(
                    "已上传图像/音频但尚未生成多模态 evidence facts（需配置 VLM 或音频转写）"
                )
        except Exception as mm_err:
            logger.warning(f"加载多模态上下文失败: {mm_err}")

        return context

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