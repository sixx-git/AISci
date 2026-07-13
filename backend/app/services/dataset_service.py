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
from app.skills.data.dataset_semantic_understanding_skill import (
    DatasetSemanticUnderstandingSkill,
    llm_csv_parse_diagnostic,
    merge_semantic_into_metadata,
)
from app.skills.data_finder.file_format_registry import (
    CHEMISTRY_EXTENSIONS,
    is_allowed_upload_filename,
    is_chemistry_format,
)

logger = logging.getLogger(__name__)

_MAX_PREVIEW_ROWS = 5
_MAX_STATISTICS_COLS = 30
_MAX_JSON_CHARS = 48_000

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".txt", ".md",
                        ".png", ".jpg", ".jpeg", ".tiff", ".webp", ".gif",
                        ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac",
                        ".npy", ".npz", ".zip"} | CHEMISTRY_EXTENSIONS
TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff"}
TIME_SERIES_EXTENSIONS = {".wav", ".npy", ".npz"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}
JSON_EXTENSIONS = {".json", ".jsonl"}


def _json_dumps_bounded(obj: Any, max_chars: int = _MAX_JSON_CHARS) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = json.dumps({"_error": "json_encode_failed"}, ensure_ascii=False)
    if len(text) <= max_chars:
        return text
    return json.dumps(
        {"_truncated": True, "preview": text[: min(2000, max_chars - 80)] + "…"},
        ensure_ascii=False,
    )


def _cap_statistics(stats: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(stats, dict):
        return {}
    capped: Dict[str, Any] = {}
    for idx, (col, val) in enumerate(stats.items()):
        if idx >= _MAX_STATISTICS_COLS:
            capped["_truncated_columns"] = len(stats) - _MAX_STATISTICS_COLS
            break
        if isinstance(val, dict) and "top_values" in val and isinstance(val["top_values"], dict):
            val = {**val, "top_values": dict(list(val["top_values"].items())[:5])}
        capped[col] = val
    return capped


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

    async def save_uploaded_file_stream(
        self,
        project_id: str,
        filename: str,
        upload_file,
        *,
        max_bytes: Optional[int] = None,
    ) -> tuple[str, int]:
        """流式写入磁盘，避免大文件整包进内存。"""
        settings = get_settings()
        limit = int(max_bytes if max_bytes is not None else settings.MAX_UPLOAD_SIZE)
        chunk_size = max(64 * 1024, int(settings.UPLOAD_CHUNK_SIZE))
        ds_dir = self._get_storage_dir(project_id)
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        file_path = os.path.join(ds_dir, safe_name)
        total = 0
        with open(file_path, "wb") as out:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    out.close()
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                    raise ValueError(
                        f"文件大小超过限制 ({limit / (1024 * 1024):.0f} MB)。"
                        "可在 .env 中调整 MAX_UPLOAD_SIZE。"
                    )
                out.write(chunk)
        return file_path, total

    @staticmethod
    def _populate_result_from_probe(result: Dict[str, Any], probe: Dict[str, Any]) -> None:
        """将 DuckDB probe 结果写入 analyze_tabular_preview 返回值。"""
        n_rows = probe.get("n_rows")
        if n_rows is None and isinstance(probe.get("row_count_est"), int):
            n_rows = probe["row_count_est"]
        result.update({
            "columns": probe.get("columns") or [],
            "dtypes": probe.get("dtypes") or {},
            "n_rows": int(n_rows) if isinstance(n_rows, int) else 0,
            "n_columns": int(probe.get("n_columns") or 0),
            "missing_count": probe.get("missing_count") or 0,
            "missing_rate": probe.get("missing_rate") or 0.0,
            "statistics": probe.get("statistics") or {},
            "preview": (probe.get("preview") or [])[:_MAX_PREVIEW_ROWS],
            "_large_file_probe": bool(probe.get("file_size_bytes")),
            "analysis_tier": probe.get("analysis_tier"),
            "probe_engine": probe.get("probe_engine"),
            "row_count_est": probe.get("row_count_est"),
            "sample_parquet_path": probe.get("sample_parquet_path"),
        })

    @staticmethod
    def _guess_csv_separator(file_path: str) -> Optional[str]:
        """根据首行分隔符密度推断 CSV 分隔符。"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                header = fh.readline()
        except OSError:
            return None
        if not header.strip():
            return None
        candidates = [(";", header.count(";")), (",", header.count(",")), ("\t", header.count("\t")), ("|", header.count("|"))]
        best_sep, best_count = max(candidates, key=lambda item: item[1])
        return best_sep if best_count > 0 else None

    @staticmethod
    def _read_tabular_dataframe(file_path: str, *, nrows: Optional[int] = None):
        """尝试多种分隔符读取 CSV/TSV，兼容欧洲分号格式与含逗号文本字段。"""
        import pandas as pd

        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path, nrows=nrows)
        if ext == ".json":
            return pd.read_json(file_path)
        if ext == ".jsonl":
            return pd.read_json(file_path, lines=True)

        read_kwargs = {"nrows": nrows} if nrows is not None else {}
        guessed = DatasetService._guess_csv_separator(file_path)
        attempts: list[dict] = []
        if guessed:
            attempts.append({"sep": guessed})
        attempts.extend([
            {},
            {"sep": ";"},
            {"sep": "\t"},
            {"sep": "|"},
            {"sep": None, "engine": "python"},
        ])
        seen = set()
        ordered_attempts = []
        for extra in attempts:
            key = tuple(sorted(extra.items()))
            if key in seen:
                continue
            seen.add(key)
            ordered_attempts.append(extra)

        last_error: Optional[Exception] = None
        best_df = None
        for extra in ordered_attempts:
            try:
                df = pd.read_csv(file_path, **read_kwargs, **extra)
                if len(df.columns) <= 1 and guessed and extra.get("sep") != guessed:
                    continue
                if best_df is None or len(df.columns) > len(best_df.columns):
                    best_df = df
                if len(df.columns) > 1:
                    return df
            except Exception as exc:
                last_error = exc
        if best_df is not None:
            return best_df
        if last_error:
            raise last_error
        raise ValueError(f"无法解析表格文件: {file_path}")

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
            settings = get_settings()
            file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
            if file_size > int(settings.LARGE_FILE_THRESHOLD_BYTES):
                from app.services.data_probe_service import get_data_probe_service

                probe = get_data_probe_service().probe_tabular(file_path)
                if probe.get("probe_status") == "completed":
                    result.update({
                        "columns": probe.get("columns") or [],
                        "dtypes": probe.get("dtypes") or {},
                        "n_rows": probe.get("n_rows") or 0,
                        "n_columns": probe.get("n_columns") or 0,
                        "missing_count": probe.get("missing_count") or 0,
                        "missing_rate": probe.get("missing_rate") or 0.0,
                        "statistics": probe.get("statistics") or {},
                        "preview": (probe.get("preview") or [])[:_MAX_PREVIEW_ROWS],
                        "_large_file_probe": True,
                        "analysis_tier": probe.get("analysis_tier"),
                        "probe_engine": probe.get("probe_engine"),
                        "row_count_est": probe.get("row_count_est"),
                        "sample_parquet_path": probe.get("sample_parquet_path"),
                    })
                    return result

            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".csv", ".tsv", ".txt") and file_size <= int(settings.LARGE_FILE_THRESHOLD_BYTES):
                from app.services.data_probe_service import get_data_probe_service

                probe = get_data_probe_service().probe_tabular(file_path)
                if probe.get("probe_status") == "completed" and (probe.get("columns") or probe.get("n_columns")):
                    self._populate_result_from_probe(result, probe)
                    return result

            df = self._read_tabular_dataframe(file_path)

            result["columns"] = list(df.columns)
            result["dtypes"] = {c: str(dt) for c, dt in df.dtypes.to_dict().items()}
            result["n_rows"] = int(len(df))
            result["n_columns"] = int(len(df.columns))
            total_cells = result["n_rows"] * max(result["n_columns"], 1)
            missing_cells = int(df.isnull().sum().sum())
            result["missing_count"] = missing_cells
            result["missing_rate"] = round(missing_cells / total_cells, 4) if total_cells > 0 else 0.0

            import pandas as pd

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
            result["statistics"] = _cap_statistics(stats)
            result["preview"] = json.loads(
                df.head(n_preview).to_json(orient="records", force_ascii=False)
            )[:_MAX_PREVIEW_ROWS]
        except Exception as e:
            logger.warning(f"分析表格数据失败: {e}")
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".csv", ".tsv", ".txt") and os.path.isfile(file_path):
                try:
                    from app.services.data_probe_service import get_data_probe_service

                    probe = get_data_probe_service().probe_tabular(file_path)
                    if probe.get("probe_status") == "completed":
                        self._populate_result_from_probe(result, probe)
                except Exception as probe_err:
                    logger.warning("DuckDB 探查兜底失败: %s", probe_err)
        if (
            result.get("n_rows", 0) == 0
            and os.path.isfile(file_path)
            and os.path.splitext(file_path)[1].lower() in (".csv", ".tsv", ".txt")
        ):
            recovered = self._try_llm_parse_recovery(file_path, n_preview)
            if recovered and recovered.get("n_rows", 0) > 0:
                result.update(recovered)
        return result

    def _try_llm_parse_recovery(self, file_path: str, n_preview: int = 10) -> Optional[Dict[str, Any]]:
        """探查结果为 0 时，用 LLM 诊断分隔符并重试 pandas 读取。"""
        diagnostic = llm_csv_parse_diagnostic(file_path)
        if not diagnostic or float(diagnostic.get("confidence") or 0) < 0.3:
            return None
        sep = diagnostic.get("separator")
        if not sep:
            return None
        try:
            import pandas as pd

            read_kwargs: Dict[str, Any] = {"sep": sep}
            skip_rows = int(diagnostic.get("skip_rows") or 0)
            if skip_rows > 0:
                read_kwargs["skiprows"] = skip_rows
            encoding = diagnostic.get("encoding")
            if encoding:
                read_kwargs["encoding"] = encoding
            if diagnostic.get("has_header") is False:
                read_kwargs["header"] = None

            df = pd.read_csv(file_path, **read_kwargs)
            if len(df.columns) <= 1 or len(df) == 0:
                return None

            result: Dict[str, Any] = {
                "columns": list(df.columns),
                "dtypes": {c: str(dt) for c, dt in df.dtypes.to_dict().items()},
                "n_rows": int(len(df)),
                "n_columns": int(len(df.columns)),
                "missing_count": int(df.isnull().sum().sum()),
                "missing_rate": 0.0,
                "statistics": {},
                "preview": json.loads(
                    df.head(n_preview).to_json(orient="records", force_ascii=False)
                )[:_MAX_PREVIEW_ROWS],
                "parse_recovery": "llm_diagnostic",
                "parsing_notes": diagnostic.get("notes"),
            }
            total_cells = result["n_rows"] * max(result["n_columns"], 1)
            if total_cells > 0:
                result["missing_rate"] = round(result["missing_count"] / total_cells, 4)
            return result
        except Exception as exc:
            logger.warning("LLM 诊断后重试解析失败: %s", exc)
            return None

    def _get_project_research_question(self, project_id: str) -> str:
        try:
            from app.models.project import Project

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project and getattr(project, "research_question", None):
                return str(project.research_question).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _get_project_mode(project_id: str, db: Session) -> str:
        try:
            from app.models.project import Project
            from app.core.project_modes import normalize_project_mode

            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                return normalize_project_mode(getattr(project, "project_mode", None))
        except Exception:
            pass
        return "general"

    def _run_tabular_semantic_understanding(
        self,
        *,
        project_id: str,
        filename: str,
        analysis: Dict[str, Any],
        existing_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """对 tabular 探查结果运行 LLM 语义理解，失败则规则 fallback。"""
        columns = analysis.get("columns") or []
        if not columns:
            return existing_meta

        async def _run():
            skill = DatasetSemanticUnderstandingSkill()
            return await skill.run(
                input_data={
                    "filename": filename,
                    "columns": columns,
                    "dtypes": analysis.get("dtypes") or {},
                    "n_rows": analysis.get("n_rows") or 0,
                    "n_columns": analysis.get("n_columns") or len(columns),
                    "preview": analysis.get("preview") or [],
                    "statistics": analysis.get("statistics") or {},
                    "research_question": self._get_project_research_question(project_id),
                    "project_mode": self._get_project_mode(project_id, self.db),
                },
                context={"stage": "dataset_preprocessing", "project_id": project_id},
            )

        try:
            skill_result = asyncio.run(_run())
            if skill_result.success and skill_result.data:
                return merge_semantic_into_metadata(existing_meta, skill_result.data)
        except Exception as exc:
            logger.warning("数据集语义理解失败: %s", exc)
        return existing_meta

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
                            ds.columns_json = _json_dumps_bounded(analysis.get("columns", tables[0].get("columns", [])))
                            ds.dtypes_json = _json_dumps_bounded(analysis.get("dtypes", {}))
                            ds.missing_count = analysis.get("missing_count", 0)
                            ds.missing_rate = analysis.get("missing_rate", 0.0)
                            ds.statistics_json = _json_dumps_bounded(analysis.get("statistics", {}))
                            ds.preview_json = _json_dumps_bounded(analysis.get("preview", []))
                            ds.extra_metadata = _json_dumps_bounded({
                                "derived_csv_path": csv_path,
                                "extraction_method": "chem_structure",
                                "source_format": tables[0].get("format"),
                                "truncated": tables[0].get("truncated", False),
                            })
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
                    ds.columns_json = _json_dumps_bounded(analysis.get("columns", []))
                    ds.dtypes_json = _json_dumps_bounded(analysis.get("dtypes", {}))
                    ds.missing_count = analysis.get("missing_count", 0)
                    ds.missing_rate = analysis.get("missing_rate", 0.0)
                    ds.statistics_json = _json_dumps_bounded(analysis.get("statistics", {}))
                    ds.preview_json = _json_dumps_bounded(analysis.get("preview", []))
                    meta: Dict[str, Any] = {}
                    if analysis.get("_large_file_probe"):
                        meta.update({
                            "analysis_tier": analysis.get("analysis_tier"),
                            "probe_engine": analysis.get("probe_engine"),
                            "file_size_bytes": file_size or os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
                            "row_count_est": analysis.get("row_count_est") or analysis.get("n_rows"),
                            "sample_parquet_path": analysis.get("sample_parquet_path"),
                            "large_file_probe": True,
                        })
                    meta = self._run_tabular_semantic_understanding(
                        project_id=project_id,
                        filename=filename,
                        analysis=analysis,
                        existing_meta={k: v for k, v in meta.items() if v is not None},
                    )
                    if meta:
                        ds.extra_metadata = json.dumps(meta, ensure_ascii=False)
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
        """兼容旧调用方；内部委托规则 fallback。"""
        from app.skills.data.dataset_semantic_understanding_skill import rule_fallback_semantic_schema

        payload = rule_fallback_semantic_schema(columns=[str(c) for c in columns], dtypes={})
        return {
            "target_candidates": payload.get("target_candidates", {}),
            "numeric_field_candidates": payload.get("numeric_field_candidates", []),
            "categorical_field_candidates": payload.get("categorical_field_candidates", []),
            "generic_metric_candidates": payload.get("generic_metric_candidates", []),
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
                existing_meta = {}
                if ds.extra_metadata:
                    try:
                        existing_meta = json.loads(ds.extra_metadata) if isinstance(ds.extra_metadata, str) else ds.extra_metadata
                    except json.JSONDecodeError:
                        pass
                existing_meta = self._run_tabular_semantic_understanding(
                    project_id=ds.project_id,
                    filename=ds.filename,
                    analysis=analysis,
                    existing_meta=existing_meta,
                )
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
                        if extra.get("semantic_schema"):
                            ds_entry["semantic_schema"] = extra["semantic_schema"]
                            ss = extra["semantic_schema"]
                            if isinstance(ss, dict):
                                if ss.get("recommended_targets"):
                                    all_targets.extend(ss["recommended_targets"])
                                if ss.get("experiment_hints"):
                                    ds_entry["experiment_hints"] = ss["experiment_hints"]
                                if ss.get("quality_issues"):
                                    ds_entry["semantic_quality_issues"] = ss["quality_issues"]
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
            from app.services.data_finder_slim import slim_data_finder_payload

            df_results = get_data_finder_service(self.db).load_results(project_id)
            if df_results:
                context["data_finder_results"] = slim_data_finder_payload(df_results)
                merged = df_results.get("merged") or {}
                csv_path = merged.get("cleaned_csv_path") or merged.get("merged_csv_path") or merged.get("csv_path")
                if csv_path:
                    context["data_finder_merged_csv"] = csv_path
                if df_results.get("coverage_report"):
                    cov = df_results["coverage_report"]
                    if isinstance(cov, dict):
                        context["data_finder_coverage"] = {
                            "overall_score": cov.get("overall_score"),
                            "coverage_score": cov.get("coverage_score"),
                            "data_spec_score": cov.get("data_spec_score"),
                        }
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
        from app.core.dataset_scale import parse_dataset_extra_metadata, dataset_analysis_tier

        meta = parse_dataset_extra_metadata(ds.extra_metadata)
        tier = dataset_analysis_tier(ds)
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
            "analysis_tier": tier,
            "row_count_est": meta.get("row_count_est"),
            "sample_parquet_path": meta.get("sample_parquet_path"),
            "probe_engine": meta.get("probe_engine"),
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
            "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
        }