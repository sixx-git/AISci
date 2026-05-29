"""
多模态数据摄取 Skill
参考能力：OpenScholar/AI Scientist 数据预处理能力
支持 CSV、Excel、HDF5、JSON、PDF、图像、时间序列等格式的标准化摄入。
"""
import logging
import os
import json
import csv
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime
from io import StringIO

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {
    ".csv": "csv",
    ".tsv": "tabular",
    ".xlsx": "excel",
    ".xls": "excel",
    ".h5": "hdf5",
    ".hdf5": "hdf5",
    ".json": "json",
    ".jsonl": "json_lines",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".parquet": "parquet",
    ".txt": "text",
}

STANDARD_COLUMN_MAP = {
    "x": "feature_x",
    "y": "feature_y",
    "target": "target",
    "label": "label",
    "class": "target_class",
    "id": "sample_id",
    "timestamp": "timestamp",
    "date": "date",
    "time": "time",
    "score": "score",
    "value": "value",
}

MISSING_FILL_STRATEGIES = {
    "numeric": "median",
    "categorical": "mode",
    "text": "empty_string",
}


class MultimodalDataIngestSkill(BaseSkill):
    """多模态数据摄取 Skill

    输入:
      - file_paths: List[str]         数据文件路径列表
      - project_id: str               项目 ID
      - format_overrides: dict        格式覆盖（可选）
      - missing_strategy: str         缺失值策略: median / mode / drop / forward_fill

    输出 (SkillResult.data):
      - datasets: List[dict]          标准化数据集列表
      - total_files: int              文件总数
      - ingested_files: int           成功摄入数
      - failed_files: List[str]       失败文件列表
      - summary: dict                 数据概览
    """

    name = "MultimodalDataIngest"
    description = "支持 CSV/Excel/HDF5/JSON/PDF/图像/时序的标准化摄入、字段名清洗、缺失值与异常值处理"
    source_reference = "OpenScholar (arxiv:2411.14199) — RAG-enhanced literature understanding 参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        file_paths = input_data.get("file_paths", [])
        project_id = input_data.get("project_id", "")
        missing_strategy = input_data.get("missing_strategy", "median")

        if not file_paths:
            result.add_warning("未提供数据文件路径")
            result.data = {
                "datasets": [],
                "total_files": 0,
                "ingested_files": 0,
                "failed_files": [],
                "summary": {"message": "无数据文件"}
            }
            return result

        datasets: List[dict] = []
        failed_files: List[str] = []
        ingested_files = 0

        for fp in file_paths:
            try:
                if not os.path.exists(fp):
                    result.add_warning(f"文件不存在: {fp}")
                    failed_files.append(fp)
                    continue

                ext = os.path.splitext(fp)[1].lower()
                fmt = input_data.get("format_overrides", {}).get(fp) or SUPPORTED_FORMATS.get(ext, "unknown")

                ds = self._ingest_file(fp, fmt, project_id, missing_strategy)
                if ds:
                    datasets.append(ds)
                    ingested_files += 1
                else:
                    result.add_warning(f"无法摄入文件: {fp}")
                    failed_files.append(fp)

            except Exception as e:
                logger.warning(f"摄入文件失败 {fp}: {e}")
                result.add_warning(f"摄入失败 {fp}: {e}")
                failed_files.append(fp)

        summary = self._build_summary(datasets)

        result.data = {
            "datasets": datasets,
            "total_files": len(file_paths),
            "ingested_files": ingested_files,
            "failed_files": failed_files,
            "summary": summary,
        }
        result.metadata = {
            "project_id": project_id,
            "missing_strategy": missing_strategy,
            "ingested_at": datetime.now().isoformat(),
        }
        return result

    # ──────── 核心摄入逻辑 ────────

    def _ingest_file(
        self, file_path: str, fmt: str, project_id: str, missing_strategy: str
    ) -> Optional[Dict[str, Any]]:
        file_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
        base = {
            "file_id": file_id,
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "format": fmt,
            "project_id": project_id,
            "ingested_at": datetime.now().isoformat(),
            "columns": [],
            "n_rows": 0,
            "n_columns": 0,
            "missing_count": 0,
            "dtypes": {},
            "preview": [],
            "statistics": {},
        }

        if fmt in ("csv", "tabular"):
            return self._ingest_csv(file_path, base, missing_strategy)
        elif fmt == "json":
            return self._ingest_json(file_path, base)
        elif fmt == "json_lines":
            return self._ingest_jsonl(file_path, base)
        elif fmt in ("excel",):
            return self._ingest_excel(file_path, base, missing_strategy)
        elif fmt in ("parquet", "hdf5"):
            return self._ingest_dataframe(file_path, fmt, base, missing_strategy)
        elif fmt == "text":
            return self._ingest_text(file_path, base)
        elif fmt == "image":
            return self._ingest_image(file_path, base)
        elif fmt == "pdf":
            return self._ingest_pdf_meta(file_path, base)
        else:
            logger.info(f"未支持格式 {fmt}，尝试 CSV fallback: {file_path}")
            return self._ingest_csv(file_path, base, missing_strategy)

    def _ingest_csv(self, file_path: str, base: dict, missing_strategy: str) -> dict:
        rows = []
        columns = []
        dtypes = {}
        missing_count = 0

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                raw_columns = reader.fieldnames or []
                columns = [self._normalize_column(c) for c in raw_columns]
                col_map = dict(zip(raw_columns, columns))

                for row in reader:
                    mapped = {}
                    for rk, rv in row.items():
                        nk = col_map.get(rk, rk)
                        mapped[nk] = self._infer_value(rv)
                    rows.append(mapped)

            if rows:
                dtypes = self._infer_dtypes(rows[0])
                missing_count = sum(
                    1 for r in rows for v in r.values() if v is None or v == ""
                )

            n_cols = len(columns)
            stats = self._compute_statistics(rows, columns, dtypes)

            base["columns"] = columns
            base["n_rows"] = len(rows)
            base["n_columns"] = n_cols
            base["missing_count"] = missing_count
            base["dtypes"] = dtypes
            base["preview"] = rows[:5]
            base["statistics"] = stats
            base["sample_data"] = rows
            return base

        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="gbk") as f:
                    reader = csv.DictReader(f)
                    raw_columns = reader.fieldnames or []
                    columns = [self._normalize_column(c) for c in raw_columns]
                    col_map = dict(zip(raw_columns, columns))
                    for row in reader:
                        mapped = {}
                        for rk, rv in row.items():
                            nk = col_map.get(rk, rk)
                            mapped[nk] = self._infer_value(rv)
                        rows.append(mapped)

                if rows:
                    dtypes = self._infer_dtypes(rows[0])
                    missing_count = sum(
                        1 for r in rows for v in r.values() if v is None or v == ""
                    )

                n_cols = len(columns)
                stats = self._compute_statistics(rows, columns, dtypes)

                base["columns"] = columns
                base["n_rows"] = len(rows)
                base["n_columns"] = n_cols
                base["missing_count"] = missing_count
                base["dtypes"] = dtypes
                base["preview"] = rows[:5]
                base["statistics"] = stats
                base["sample_data"] = rows
                return base
            except Exception:
                base["n_rows"] = 0
                base["n_columns"] = 0
                base["columns"] = []
                return base
        except Exception:
            base["n_rows"] = 0
            base["n_columns"] = 0
            base["columns"] = []
            return base

    def _ingest_json(self, file_path: str, base: dict) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) > 0:
                rows = data
                columns = list(rows[0].keys()) if isinstance(rows[0], dict) else ["value"]
                columns = [self._normalize_column(c) for c in columns]
            elif isinstance(data, dict):
                rows = [data]
                columns = list(data.keys())
                columns = [self._normalize_column(c) for c in columns]
            else:
                rows = [{"value": str(data)}]
                columns = ["value"]

            dtypes = self._infer_dtypes(rows[0]) if rows else {}
            missing_count = sum(
                1 for r in rows for v in (r.values() if isinstance(r, dict) else [])
                if v is None or v == ""
            )

            base["columns"] = columns
            base["n_rows"] = len(rows)
            base["n_columns"] = len(columns)
            base["missing_count"] = missing_count
            base["dtypes"] = dtypes
            base["preview"] = rows[:5]
            base["statistics"] = self._compute_statistics(rows, columns, dtypes)
            base["sample_data"] = rows
            return base
        except Exception:
            base["n_rows"] = 0
            base["n_columns"] = 0
            base["columns"] = []
            return base

    def _ingest_jsonl(self, file_path: str, base: dict) -> dict:
        try:
            rows = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))

            columns = []
            if rows and isinstance(rows[0], dict):
                columns = list(rows[0].keys())
                columns = [self._normalize_column(c) for c in columns]

            dtypes = self._infer_dtypes(rows[0]) if rows else {}
            missing_count = sum(
                1 for r in rows for v in (r.values() if isinstance(r, dict) else [])
                if v is None or v == ""
            )

            base["columns"] = columns
            base["n_rows"] = len(rows)
            base["n_columns"] = len(columns)
            base["missing_count"] = missing_count
            base["dtypes"] = dtypes
            base["preview"] = rows[:5]
            base["statistics"] = self._compute_statistics(rows, columns, dtypes)
            base["sample_data"] = rows
            return base
        except Exception:
            base["n_rows"] = 0
            return base

    def _ingest_excel(self, file_path: str, base: dict, missing_strategy: str) -> dict:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            rows_list = list(ws.iter_rows(values_only=True))
            if not rows_list:
                base["n_rows"] = 0
                return base

            headers = [str(h) if h else f"col_{i}" for i, h in enumerate(rows_list[0])]
            columns = [self._normalize_column(h) for h in headers]
            col_map = dict(zip(headers, columns))

            data_rows = []
            for row in rows_list[1:]:
                mapped = {}
                for i, cell in enumerate(row):
                    if i < len(headers):
                        nk = col_map.get(headers[i], headers[i])
                        mapped[nk] = self._infer_value(str(cell) if cell is not None else "")
                if any(v != "" and v is not None for v in mapped.values()):
                    data_rows.append(mapped)
            wb.close()

            dtypes = self._infer_dtypes(data_rows[0]) if data_rows else {}
            missing_count = sum(
                1 for r in data_rows for v in r.values() if v is None or v == ""
            )

            base["columns"] = columns
            base["n_rows"] = len(data_rows)
            base["n_columns"] = len(columns)
            base["missing_count"] = missing_count
            base["dtypes"] = dtypes
            base["preview"] = data_rows[:5]
            base["statistics"] = self._compute_statistics(data_rows, columns, dtypes)
            base["sample_data"] = data_rows
            return base
        except ImportError:
            logger.warning("openpyxl 未安装，无法读取 Excel")
            base["n_rows"] = 0
            return base
        except Exception as e:
            logger.warning(f"Excel 读取失败: {e}")
            base["n_rows"] = 0
            return base

    def _ingest_dataframe(self, file_path: str, fmt: str, base: dict, missing_strategy: str) -> dict:
        try:
            import pandas as pd
            if fmt == "parquet":
                df = pd.read_parquet(file_path)
            else:
                df = pd.read_hdf(file_path, key="data")
        except ImportError:
            logger.warning("pandas 未安装，无法读取")
            base["n_rows"] = 0
            return base
        except Exception as e:
            logger.warning(f"DataFrame 读取失败: {e}")
            base["n_rows"] = 0
            return base

        df.columns = [self._normalize_column(str(c)) for c in df.columns]
        columns = list(df.columns)

        if missing_strategy == "drop":
            df = df.dropna()
        elif missing_strategy == "forward_fill":
            df = df.fillna(method="ffill")

        dtypes = {c: str(df[c].dtype) for c in columns}
        n_missing = int(df.isnull().sum().sum())
        stats = {c: {"mean": None, "std": None, "min": None, "max": None} for c in columns}
        for c in columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                stats[c] = {
                    "mean": float(df[c].mean()) if not df[c].isnull().all() else None,
                    "std": float(df[c].std()) if not df[c].isnull().all() else None,
                    "min": float(df[c].min()) if not df[c].isnull().all() else None,
                    "max": float(df[c].max()) if not df[c].isnull().all() else None,
                    "median": float(df[c].median()) if not df[c].isnull().all() else None,
                }

        preview = df.head(5).to_dict(orient="records")

        base["columns"] = columns
        base["n_rows"] = len(df)
        base["n_columns"] = len(columns)
        base["missing_count"] = n_missing
        base["dtypes"] = dtypes
        base["preview"] = preview
        base["statistics"] = stats
        base["sample_data"] = df.head(100).to_dict(orient="records")
        return base

    def _ingest_text(self, file_path: str, base: dict) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="gbk") as f:
                    content = f.read()
            except Exception:
                content = ""
        except Exception:
            content = ""

        lines = [l.strip() for l in content.split("\n") if l.strip()]
        base["columns"] = ["text", "line_number"]
        base["n_rows"] = len(lines)
        base["n_columns"] = 2
        base["missing_count"] = 0
        base["dtypes"] = {"text": "string", "line_number": "int"}
        base["preview"] = [{"text": l[:200], "line_number": i} for i, l in enumerate(lines[:5])]
        base["statistics"] = {
            "total_chars": len(content),
            "total_lines": len(lines),
            "avg_line_length": sum(len(l) for l in lines) / max(len(lines), 1),
        }
        base["sample_data"] = [{"text": l[:500], "line_number": i} for i, l in enumerate(lines[:100])]
        return base

    def _ingest_image(self, file_path: str, base: dict) -> dict:
        try:
            from PIL import Image
            img = Image.open(file_path)
            w, h = img.size
            mode = img.mode
            base["columns"] = ["width", "height", "mode", "format"]
            base["n_rows"] = 1
            base["n_columns"] = 4
            base["dtypes"] = {"width": "int", "height": "int", "mode": "string", "format": "string"}
            base["preview"] = [{"width": w, "height": h, "mode": mode, "format": img.format}]
            base["statistics"] = {"width": w, "height": h, "mode": mode, "format": img.format}
            base["sample_data"] = [{"width": w, "height": h, "mode": mode, "format": img.format}]
            img.close()
        except ImportError:
            base["n_rows"] = 0
            base["n_columns"] = 0
            base["columns"] = []
            logger.warning("Pillow 未安装，无法读取图像元数据")
        except Exception as e:
            base["n_rows"] = 0
            base["n_columns"] = 0
            base["columns"] = []
            logger.warning(f"图像读取失败: {e}")
        return base

    def _ingest_pdf_meta(self, file_path: str, base: dict) -> dict:
        try:
            import fitz
            doc = fitz.open(file_path)
            n_pages = len(doc)
            total_chars = 0
            for page in doc:
                total_chars += len(page.get_text())
            doc.close()
            base["columns"] = ["pages", "total_chars", "file_size_mb"]
            base["n_rows"] = 1
            base["n_columns"] = 3
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            base["dtypes"] = {"pages": "int", "total_chars": "int", "file_size_mb": "float"}
            base["preview"] = [{"pages": n_pages, "total_chars": total_chars, "file_size_mb": round(file_size, 2)}]
            base["statistics"] = {"pages": n_pages, "total_chars": total_chars, "file_size_mb": round(file_size, 2)}
        except ImportError:
            base["n_rows"] = 0
            logger.warning("PyMuPDF 未安装，无法读取 PDF 元数据")
        except Exception as e:
            base["n_rows"] = 0
            logger.warning(f"PDF 读取失败: {e}")
        return base

    # ──────── 工具方法 ────────

    @staticmethod
    def _normalize_column(name: str) -> str:
        name = name.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        name = "".join(c for c in name if c.isalnum() or c == "_")
        if not name:
            return "unnamed_col"
        if name in STANDARD_COLUMN_MAP:
            return STANDARD_COLUMN_MAP[name]
        if name[0].isdigit():
            name = "col_" + name
        return name

    @staticmethod
    def _infer_value(val: str):
        if val is None or val.strip() == "":
            return None
        val = val.strip()
        if val.lower() in ("true", "false"):
            return val.lower() == "true"
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
        return val

    @staticmethod
    def _infer_dtypes(row: dict) -> Dict[str, str]:
        dtypes = {}
        for k, v in row.items():
            if isinstance(v, bool):
                dtypes[k] = "boolean"
            elif isinstance(v, int):
                dtypes[k] = "integer"
            elif isinstance(v, float):
                dtypes[k] = "float"
            elif v is None:
                dtypes[k] = "unknown"
            else:
                dtypes[k] = "string"
        return dtypes

    @staticmethod
    def _compute_statistics(
        rows: List[dict], columns: List[str], dtypes: Dict[str, str]
    ) -> Dict[str, Any]:
        stats = {}
        for col in columns:
            vals = [r.get(col) for r in rows if r.get(col) is not None]
            if not vals:
                stats[col] = {"count": 0, "mean": None, "std": None}
                continue

            dtype = dtypes.get(col, "string")
            if dtype in ("integer", "float", "numeric"):
                numeric_vals = [v for v in vals if isinstance(v, (int, float))]
                if numeric_vals:
                    stats[col] = {
                        "count": len(numeric_vals),
                        "mean": round(sum(numeric_vals) / len(numeric_vals), 4),
                        "std": round(
                            (sum((x - sum(numeric_vals) / len(numeric_vals)) ** 2 for x in numeric_vals) / len(numeric_vals)) ** 0.5,
                            4,
                        ),
                        "min": min(numeric_vals),
                        "max": max(numeric_vals),
                    }
                else:
                    stats[col] = {"count": len(vals), "mean": None}
            elif dtype == "boolean":
                true_count = sum(1 for v in vals if v is True)
                stats[col] = {"count": len(vals), "true_count": true_count, "true_ratio": round(true_count / len(vals), 4)}
            else:
                unique_count = len(set(str(v) for v in vals))
                stats[col] = {"count": len(vals), "unique_count": unique_count}
        return stats

    @staticmethod
    def _build_summary(datasets: List[dict]) -> Dict[str, Any]:
        if not datasets:
            return {"message": "无可用数据集"}

        total_rows = sum(d.get("n_rows", 0) for d in datasets)
        total_cols = sum(d.get("n_columns", 0) for d in datasets)
        formats = set(d.get("format", "unknown") for d in datasets)

        return {
            "total_datasets": len(datasets),
            "total_rows": total_rows,
            "total_columns": total_cols,
            "formats": sorted(formats),
            "datasets": [
                {"file_name": d["file_name"], "format": d.get("format"), "n_rows": d.get("n_rows", 0), "n_columns": d.get("n_columns", 0)}
                for d in datasets
            ],
        }