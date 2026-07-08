"""大文件数据探查 — DuckDB 优先，pandas 采样兜底。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.dataset_scale import resolve_analysis_tier

logger = logging.getLogger(__name__)


class DataProbeService:
    """对 tabular 文件做分级探查，产出可写入 Dataset 的摘要。"""

    def probe_tabular(self, file_path: str, *, filename: str = "") -> Dict[str, Any]:
        if not os.path.isfile(file_path):
            return {"probe_status": "failed", "error": "file not found"}

        size = os.path.getsize(file_path)
        tier = resolve_analysis_tier(size)
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".csv", ".tsv", ".txt"):
            return {
                "probe_status": "skipped",
                "analysis_tier": tier,
                "file_size_bytes": size,
                "reason": f"unsupported ext {ext} for duckdb probe",
            }

        try:
            return self._probe_with_duckdb(file_path, size=size, tier=tier, filename=filename)
        except Exception as duck_err:
            logger.warning("DuckDB 探查失败，回退 pandas 采样: %s", duck_err)
            return self._probe_with_pandas_sample(file_path, size=size, tier=tier, error=str(duck_err))

    def _probe_with_duckdb(
        self,
        file_path: str,
        *,
        size: int,
        tier: str,
        filename: str,
    ) -> Dict[str, Any]:
        import duckdb

        settings = get_settings()
        sample_n = max(100, int(settings.DATA_PROBE_SAMPLE_ROWS))
        con = duckdb.connect()
        escaped = file_path.replace("'", "''")
        read_expr = f"read_csv_auto('{escaped}', sample_size=-1, ignore_errors=true)"

        n_rows = int(con.execute(f"SELECT COUNT(*) FROM {read_expr}").fetchone()[0])
        cols_info = con.execute(f"DESCRIBE SELECT * FROM {read_expr}").fetchall()
        columns = [str(row[0]) for row in cols_info]
        dtypes = {str(row[0]): str(row[1]) for row in cols_info}

        sample_df = con.execute(f"SELECT * FROM {read_expr} LIMIT {sample_n}").df()

        from app.services.dataset_service import _cap_statistics

        statistics: Dict[str, Any] = {}
        missing_total = 0
        for col in sample_df.columns:
            nulls = int(sample_df[col].isnull().sum())
            missing_total += nulls
            if sample_df[col].dtype.kind in "iufc":
                statistics[col] = {
                    "mean": round(float(sample_df[col].mean()), 4) if nulls < len(sample_df) else None,
                    "std": round(float(sample_df[col].std()), 4) if nulls < len(sample_df) else None,
                    "min": float(sample_df[col].min()) if nulls < len(sample_df) else None,
                    "max": float(sample_df[col].max()) if nulls < len(sample_df) else None,
                    "missing": nulls,
                    "_from_sample": True,
                }
            else:
                top = sample_df[col].value_counts().head(5).to_dict()
                statistics[col] = {
                    "unique": int(sample_df[col].nunique()),
                    "top_values": {str(k): int(v) for k, v in top.items()},
                    "missing": nulls,
                    "_from_sample": True,
                }

        sample_cells = max(len(sample_df) * max(len(columns), 1), 1)
        missing_rate = round(missing_total / sample_cells, 4)

        sample_parquet_path = self._write_sample_parquet(file_path, sample_df, tier)

        preview = json.loads(sample_df.head(5).to_json(orient="records", force_ascii=False))

        return {
            "probe_status": "completed",
            "probe_engine": "duckdb",
            "analysis_tier": tier,
            "file_size_bytes": size,
            "n_rows": n_rows,
            "n_columns": len(columns),
            "columns": columns,
            "dtypes": dtypes,
            "missing_count": missing_total,
            "missing_rate": missing_rate,
            "statistics": _cap_statistics(statistics),
            "preview": preview,
            "sample_parquet_path": sample_parquet_path,
            "sample_rows_for_stats": len(sample_df),
            "row_count_est": n_rows,
        }

    def _probe_with_pandas_sample(
        self,
        file_path: str,
        *,
        size: int,
        tier: str,
        error: str = "",
    ) -> Dict[str, Any]:
        import pandas as pd

        settings = get_settings()
        nrows = max(100, int(settings.DATA_PROBE_SAMPLE_ROWS))
        df = pd.read_csv(file_path, nrows=nrows)

        from app.services.dataset_service import _cap_statistics

        statistics: Dict[str, Any] = {}
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                statistics[col] = {
                    "mean": round(float(df[col].mean()), 4) if not df[col].isnull().all() else None,
                    "std": round(float(df[col].std()), 4) if not df[col].isnull().all() else None,
                    "min": float(df[col].min()) if not df[col].isnull().all() else None,
                    "max": float(df[col].max()) if not df[col].isnull().all() else None,
                    "missing": int(df[col].isnull().sum()),
                    "_from_sample": True,
                }
            else:
                top_vals = df[col].value_counts().head(5).to_dict()
                statistics[col] = {
                    "unique": int(df[col].nunique()),
                    "top_values": {str(k): int(v) for k, v in top_vals.items()},
                    "missing": int(df[col].isnull().sum()),
                    "_from_sample": True,
                }

        total_cells = len(df) * max(len(df.columns), 1)
        missing_cells = int(df.isnull().sum().sum())

        return {
            "probe_status": "completed",
            "probe_engine": "pandas_sample",
            "probe_fallback_reason": error or None,
            "analysis_tier": tier,
            "file_size_bytes": size,
            "n_rows": None,
            "row_count_est": f">{nrows} (sample only)",
            "n_columns": int(len(df.columns)),
            "columns": list(df.columns),
            "dtypes": {c: str(dt) for c, dt in df.dtypes.to_dict().items()},
            "missing_count": missing_cells,
            "missing_rate": round(missing_cells / total_cells, 4) if total_cells else 0.0,
            "statistics": _cap_statistics(statistics),
            "preview": json.loads(df.head(5).to_json(orient="records", force_ascii=False)),
            "sample_rows_for_stats": len(df),
        }

    @staticmethod
    def _write_sample_parquet(file_path: str, sample_df, tier: str) -> Optional[str]:
        if tier == "T0" or sample_df is None or sample_df.empty:
            return None
        try:
            out_dir = os.path.join(os.path.dirname(file_path), "samples")
            os.makedirs(out_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(file_path))[0]
            out_path = os.path.join(out_dir, f"{base}_sample.parquet")
            sample_df.to_parquet(out_path, index=False)
            return out_path
        except Exception as exc:
            logger.warning("写入 sample parquet 失败: %s", exc)
            return None

    def apply_probe_to_dataset_fields(self, probe: Dict[str, Any]) -> Dict[str, Any]:
        """将 probe 结果转为 create_dataset 可写字段。"""
        from app.services.dataset_service import _json_dumps_bounded
        meta = {
            "analysis_tier": probe.get("analysis_tier"),
            "probe_status": probe.get("probe_status"),
            "probe_engine": probe.get("probe_engine"),
            "file_size_bytes": probe.get("file_size_bytes"),
            "sample_parquet_path": probe.get("sample_parquet_path"),
            "row_count_est": probe.get("row_count_est") or probe.get("n_rows"),
            "sample_rows_for_stats": probe.get("sample_rows_for_stats"),
        }
        if probe.get("probe_fallback_reason"):
            meta["probe_fallback_reason"] = probe["probe_fallback_reason"]

        n_rows = probe.get("n_rows")
        if n_rows is None and isinstance(probe.get("row_count_est"), int):
            n_rows = probe["row_count_est"]

        return {
            "n_rows": n_rows if isinstance(n_rows, int) else None,
            "n_columns": probe.get("n_columns") or 0,
            "columns_json": _json_dumps_bounded(probe.get("columns") or []),
            "dtypes_json": _json_dumps_bounded(probe.get("dtypes") or {}),
            "missing_count": probe.get("missing_count"),
            "missing_rate": probe.get("missing_rate"),
            "statistics_json": _json_dumps_bounded(probe.get("statistics") or {}),
            "preview_json": _json_dumps_bounded(probe.get("preview") or []),
            "extra_metadata": json.dumps({k: v for k, v in meta.items() if v is not None}, ensure_ascii=False),
            "preprocessing_status": "completed" if probe.get("probe_status") == "completed" else "failed",
        }


def get_data_probe_service() -> DataProbeService:
    return DataProbeService()
