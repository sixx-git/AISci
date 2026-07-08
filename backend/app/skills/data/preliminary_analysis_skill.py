"""
初步分析 Skill
根据多模态数据集 + Hypothesis/ExperimentDesign 做初步分析，
输出基于真实数据的统计摘要、特征向量、图表数据和初步结果。
禁止在无数据时凭空生成结果。
"""
import logging
import hashlib
import math
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class PreliminaryAnalysisSkill(BaseSkill):
    """初步分析 Skill

    输入:
      - multimodal_datasets: List[dict]      多模态数据集（含 file_path/data_type 等元数据）
      - hypothesis: str                      假设内容
      - experiment_design: dict              实验设计
      - methods: str                         研究方法
      - metrics: str                         评估指标

    输出 (SkillResult.data):
      - summary_statistics: dict             统计摘要（基于真实数据）
      - feature_vectors: List[dict]          特征向量
      - plots: List[dict]                    图表数据规格（供 ReportChartGeneration 使用）
      - preliminary_result: dict             初步分析结论
      - correlations: List[dict]             相关性分析
      - anomalies: List[dict]                异常值检测
      - data_source_flag: str                "real_data" / "simulated" / "no_data"
      - image_summary: dict                  图像数据摘要
      - time_series_summary: dict            时序数据摘要
      - sample_data_rows: List[dict]         抽样数据行（供图表生成用）
    """

    name = "PreliminaryAnalysis"
    description = "根据多模态数据集和假设/实验设计进行统计摘要、特征向量提取和图表数据生成"
    source_reference = "AI Scientist (arxiv:2408.06292) — automated data analysis & visualization 参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        multimodal_datasets = input_data.get("multimodal_datasets", [])
        hypothesis = input_data.get("hypothesis", "")
        experiment_design = input_data.get("experiment_design", {})
        methods = input_data.get("methods", "")
        metrics = input_data.get("metrics", "")

        summary_stats: Dict[str, Any] = {}
        feature_vectors: List[dict] = []
        plots: List[dict] = []
        correlations: List[dict] = []
        anomalies: List[dict] = []
        image_summary: Dict[str, Any] = {"total_images": 0, "images": []}
        time_series_summary: Dict[str, Any] = {"total_series": 0, "series": []}
        all_sample_rows: List[dict] = []
        data_source_flag = "no_data"

        has_any_real_data = False

        for ds in multimodal_datasets:
            ds_id = ds.get("dataset_id") or ds.get("file_id") or hashlib.md5(str(ds).encode()).hexdigest()[:8]
            ds_filename = ds.get("filename") or ds.get("file_name") or ds_id
            ds_type = ds.get("data_type", "unknown")
            ds_path = ds.get("file_path", "")
            ds_columns = ds.get("columns", [])
            ds_dtypes = ds.get("dtypes", {})
            ds_n_rows = ds.get("n_rows", 0)
            ds_statistics = ds.get("statistics", {})

            if ds_type == "tabular":
                tabular_result = self._analyze_tabular_dataset(
                    ds_id, ds_filename, ds_path, ds_columns, ds_dtypes, ds_n_rows, ds_statistics, ds
                )
                if tabular_result.get("has_real_data"):
                    has_any_real_data = True
                    data_source_flag = "real_data"
                    summary_stats[ds_filename] = tabular_result["summary"]
                    feature_vectors.extend(tabular_result["feature_vectors"])
                    correlations.extend(tabular_result["correlations"])
                    anomalies.extend(tabular_result["anomalies"])
                    all_sample_rows.extend(tabular_result["sample_rows"])
                    plots.extend(tabular_result["plots"])

            elif ds_type == "image":
                img_result = self._analyze_image_dataset(ds_id, ds_filename, ds_path, ds)
                if img_result.get("has_real_data"):
                    has_any_real_data = True
                    if data_source_flag == "no_data":
                        data_source_flag = "real_data"
                    image_summary["total_images"] += img_result.get("total_images", 0)
                    image_summary["images"].extend(img_result.get("images", []))
                    summary_stats[ds_filename + " (图像)"] = img_result["summary"]

            elif ds_type == "time_series":
                ts_result = self._analyze_time_series_dataset(ds_id, ds_filename, ds_path, ds)
                if ts_result.get("has_real_data"):
                    has_any_real_data = True
                    if data_source_flag == "no_data":
                        data_source_flag = "real_data"
                    time_series_summary["total_series"] += ts_result.get("total_series", 0)
                    time_series_summary["series"].extend(ts_result.get("series", []))
                    summary_stats[ds_filename + " (时序)"] = ts_result["summary"]
                    plots.extend(ts_result["plots"])

            elif ds_type == "json":
                json_result = self._analyze_json_dataset(ds_id, ds_filename, ds_path, ds)
                if json_result.get("has_real_data"):
                    has_any_real_data = True
                    if data_source_flag == "no_data":
                        data_source_flag = "real_data"
                    summary_stats[ds_filename + " (JSON)"] = json_result["summary"]
                    feature_vectors.extend(json_result["feature_vectors"])
                    all_sample_rows.extend(json_result["sample_rows"])

            else:
                logger.info(f"Dataset {ds_filename}: data_type={ds_type}，跳过深度分析")

        if not has_any_real_data:
            result.add_warning("所有数据集均无可分析的结构化真实数据，未生成统计摘要和图表")
            result.data = {
                "summary_statistics": {},
                "feature_vectors": [],
                "plots": [],
                "preliminary_result": self._build_empty_result(hypothesis),
                "correlations": [],
                "anomalies": [],
                "data_source_flag": "no_data",
                "image_summary": image_summary,
                "time_series_summary": time_series_summary,
                "sample_data_rows": [],
            }
            result.metadata = {
                "datasets_analyzed": len(multimodal_datasets),
                "numeric_features": 0,
                "plots_generated": 0,
                "anomalies_detected": 0,
                "data_source": "no_real_data",
                "analyzed_at": datetime.now().isoformat(),
            }
            return result

        preliminary_result = self._build_preliminary_result(
            summary_stats, feature_vectors, correlations, anomalies, hypothesis
        )

        result.data = {
            "summary_statistics": summary_stats,
            "feature_vectors": feature_vectors,
            "plots": plots,
            "preliminary_result": preliminary_result,
            "correlations": correlations,
            "anomalies": anomalies,
            "data_source_flag": data_source_flag,
            "image_summary": image_summary,
            "time_series_summary": time_series_summary,
            "sample_data_rows": all_sample_rows,
        }
        result.metadata = {
            "datasets_analyzed": len(multimodal_datasets),
            "numeric_features": sum(len(fv.get("features", [])) for fv in feature_vectors),
            "plots_generated": len(plots),
            "anomalies_detected": len(anomalies),
            "data_source": data_source_flag,
            "total_images": image_summary.get("total_images", 0),
            "total_time_series": time_series_summary.get("total_series", 0),
            "analyzed_at": datetime.now().isoformat(),
        }
        return result

    def _analyze_tabular_dataset(
        self,
        ds_id: str,
        ds_filename: str,
        ds_path: str,
        ds_columns: list,
        ds_dtypes: dict,
        ds_n_rows: int,
        ds_statistics: dict,
        ds: dict,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "has_real_data": False,
            "summary": {},
            "feature_vectors": [],
            "correlations": [],
            "anomalies": [],
            "sample_rows": [],
            "plots": [],
        }

        df = None
        if ds_path and os.path.isfile(ds_path):
            try:
                import pandas as pd
                ext = os.path.splitext(ds_path)[1].lower()
                if ext in (".xlsx", ".xls"):
                    df = pd.read_excel(ds_path)
                elif ext == ".json":
                    df = pd.read_json(ds_path)
                elif ext == ".jsonl":
                    df = pd.read_json(ds_path, lines=True)
                elif ext == ".txt":
                    try:
                        df = pd.read_csv(ds_path, sep=None, engine="python")
                    except Exception:
                        df = pd.read_csv(ds_path)
                else:
                    df = pd.read_csv(ds_path)
                logger.info(f"成功读取表格文件: {ds_path}, 形状={df.shape}")
            except Exception as e:
                logger.warning(f"读取表格文件失败 {ds_path}: {e}")

        if df is None and ds_statistics:
            result["has_real_data"] = True
            result["summary"] = self._build_summary_from_stats(ds_columns, ds_dtypes, ds_n_rows, ds_statistics, ds)
            result["sample_rows"] = ds.get("preview", []) or []
            numeric_cols = [c for c, dt in ds_dtypes.items()
                            if any(k in str(dt).lower() for k in ("int", "float", "numeric"))]
            if numeric_cols:
                result["feature_vectors"].append({
                    "dataset_id": ds_id,
                    "features": numeric_cols,
                    "n_samples": ds_n_rows,
                    "feature_stats": {c: ds_statistics.get(c, {}) for c in numeric_cols if c in ds_statistics},
                })
            result["plots"] = self._build_plot_specs(ds_id, ds_filename, numeric_cols)
            return result

        if df is not None and len(df) > 0:
            result["has_real_data"] = True
            numeric_cols = []
            categorical_cols = []
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    numeric_cols.append(col)
                else:
                    categorical_cols.append(col)

            result["summary"] = {
                "n_rows": int(len(df)),
                "n_columns": int(len(df.columns)),
                "n_numeric": len(numeric_cols),
                "n_categorical": len(categorical_cols),
                "missing_total": int(df.isnull().sum().sum()),
                "missing_rate": round(float(df.isnull().sum().sum() / (len(df) * max(len(df.columns), 1))), 4),
            }

            for col in numeric_cols:
                series = df[col].dropna()
                col_stat = {
                    "mean": round(float(series.mean()), 4) if len(series) > 0 else None,
                    "std": round(float(series.std()), 4) if len(series) > 0 else None,
                    "min": round(float(series.min()), 4) if len(series) > 0 else None,
                    "max": round(float(series.max()), 4) if len(series) > 0 else None,
                    "missing": int(df[col].isnull().sum()),
                }
                result["summary"][col] = col_stat

            for col in categorical_cols[:10]:
                vc = df[col].value_counts().head(10).to_dict()
                result["summary"][f"{col}_freq"] = {str(k): int(v) for k, v in vc.items()}

            if numeric_cols:
                result["feature_vectors"].append({
                    "dataset_id": ds_id,
                    "filename": ds_filename,
                    "features": numeric_cols,
                    "n_samples": int(len(df)),
                    "feature_stats": {c: result["summary"].get(c, {}) for c in numeric_cols},
                })

                if len(numeric_cols) >= 2:
                    for i, c1 in enumerate(numeric_cols):
                        for c2 in numeric_cols[i + 1:]:
                            corr = self._compute_pearson_correlation(
                                df[c1].dropna().tolist()[:1000],
                                df[c2].dropna().tolist()[:1000],
                            )
                            if corr is not None:
                                result.setdefault("correlations", []).append({
                                    "dataset_id": ds_id,
                                    "column_x": c1,
                                    "column_y": c2,
                                    "pearson_r": corr,
                                })

                for col in numeric_cols[:6]:
                    vals = df[col].dropna().tolist()
                    if len(vals) < 2:
                        continue
                    mean_val = sum(vals) / len(vals)
                    std_val = (sum((x - mean_val) ** 2 for x in vals) / len(vals)) ** 0.5
                    if std_val == 0:
                        continue
                    threshold = 2.5 * std_val
                    for idx, v in enumerate(vals[:200]):
                        if abs(v - mean_val) > threshold:
                            result["anomalies"].append({
                                "dataset_id": ds_id,
                                "column": col,
                                "index": idx,
                                "value": round(v, 4),
                                "expected_range": [round(mean_val - threshold, 4), round(mean_val + threshold, 4)],
                                "reason": "outlier_by_std",
                            })

            sample = json.loads(df.head(100).to_json(orient="records", force_ascii=False))
            result["sample_rows"] = sample
            result["plots"] = self._build_plot_specs(ds_id, ds_filename, numeric_cols, categorical_cols)

        return result

    def _analyze_image_dataset(
        self, ds_id: str, ds_filename: str, ds_path: str, ds: dict
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "has_real_data": False,
            "total_images": 0,
            "images": [],
            "summary": {},
        }

        image_files: List[str] = []
        if ds_path and os.path.isdir(ds_path):
            for f in sorted(os.listdir(ds_path)):
                if os.path.splitext(f)[1].lower() in SUPPORTED_IMAGE_EXTENSIONS:
                    image_files.append(os.path.join(ds_path, f))
        elif ds_path and os.path.isfile(ds_path):
            ext = os.path.splitext(ds_path)[1].lower()
            if ext in SUPPORTED_IMAGE_EXTENSIONS:
                image_files.append(ds_path)

        if not image_files:
            return result

        has_pil = False
        try:
            from PIL import Image
            has_pil = True
        except ImportError:
            pass

        if not has_pil:
            result["summary"] = {
                "total_files": len(image_files),
                "note": "PIL 未安装，无法解析图像尺寸和通道。请安装: pip install Pillow",
                "file_paths": image_files[:20],
            }
            result["has_real_data"] = True
            result["total_images"] = len(image_files)
            return result

        sizes: List[Tuple[int, int]] = []
        channels: List[int] = []
        formats: Dict[str, int] = {}
        analyzed = 0

        for img_path in image_files[:100]:
            try:
                fmt = os.path.splitext(img_path)[1].lower().lstrip(".")
                formats[fmt] = formats.get(fmt, 0) + 1
                if has_pil:
                    from PIL import Image
                    with Image.open(img_path) as img:
                        sizes.append(img.size)
                        if img.mode in ("L", "1"):
                            channels.append(1)
                        elif img.mode in ("LA", "PA"):
                            channels.append(2)
                        elif img.mode == "RGB":
                            channels.append(3)
                        elif img.mode == "RGBA":
                            channels.append(4)
                        else:
                            channels.append(len(img.getbands()))
                analyzed += 1
            except Exception as e:
                logger.debug(f"无法读取图像 {img_path}: {e}")

        avg_w = round(sum(s[0] for s in sizes) / len(sizes), 1) if sizes else None
        avg_h = round(sum(s[1] for s in sizes) / len(sizes), 1) if sizes else None
        avg_c = round(sum(channels) / len(channels), 1) if channels else None
        min_size = (min(s[0] for s in sizes), min(s[1] for s in sizes)) if sizes else None
        max_size = (max(s[0] for s in sizes), max(s[1] for s in sizes)) if sizes else None

        result["has_real_data"] = True
        result["total_images"] = len(image_files)
        result["images"].append({
            "dataset_id": ds_id,
            "filename": ds_filename,
            "total": len(image_files),
            "analyzed": analyzed,
            "average_size": f"{avg_w}x{avg_h}" if avg_w else "unknown",
            "min_size": f"{min_size[0]}x{min_size[1]}" if min_size else "unknown",
            "max_size": f"{max_size[0]}x{max_size[1]}" if max_size else "unknown",
            "average_channels": avg_c,
            "formats": formats,
        })
        result["summary"] = {
            "total_images": len(image_files),
            "average_width": avg_w,
            "average_height": avg_h,
            "average_channels": avg_c,
            "min_size": f"{min_size[0]}x{min_size[1]}" if min_size else None,
            "max_size": f"{max_size[0]}x{max_size[1]}" if max_size else None,
            "file_formats": formats,
        }
        return result

    def _analyze_time_series_dataset(
        self, ds_id: str, ds_filename: str, ds_path: str, ds: dict
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "has_real_data": False,
            "total_series": 0,
            "series": [],
            "summary": {},
            "plots": [],
        }

        df = None
        if ds_path and os.path.isfile(ds_path):
            try:
                import pandas as pd
                ext = os.path.splitext(ds_path)[1].lower()
                if ext in (".xlsx", ".xls"):
                    df = pd.read_excel(ds_path)
                elif ext == ".json":
                    df = pd.read_json(ds_path)
                else:
                    df = pd.read_csv(ds_path)
            except Exception as e:
                logger.warning(f"读取时序文件失败 {ds_path}: {e}")

        if df is None:
            return result

        time_col = None
        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in ("time", "date", "timestamp", "datetime", "时间", "日期")):
                time_col = col
                break
        if time_col is None and len(df) > 0:
            try:
                pd.to_datetime(df.iloc[:, 0])
                time_col = df.columns[0]
            except Exception:
                pass

        numeric_cols = [c for c in df.columns if c != time_col and pd.api.types.is_numeric_dtype(df[c])]

        if time_col and numeric_cols:
            result["has_real_data"] = True
            result["total_series"] = len(numeric_cols)
            try:
                time_series = pd.to_datetime(df[time_col])
                time_range = {
                    "start": str(time_series.min()),
                    "end": str(time_series.max()),
                }
                diffs = time_series.diff().dropna()
                if len(diffs) > 0:
                    most_common = diffs.mode()
                    sampling_interval = str(most_common.iloc[0]) if len(most_common) > 0 else "unknown"
                else:
                    sampling_interval = "unknown"
            except Exception:
                time_range = {"start": "unknown", "end": "unknown"}
                sampling_interval = "unknown"

            result["summary"] = {
                "n_rows": int(len(df)),
                "n_series": len(numeric_cols),
                "time_column": time_col,
                "time_range": time_range,
                "sampling_interval": sampling_interval,
            }

            for col in numeric_cols:
                series = df[col].dropna()
                col_stat = {
                    "mean": round(float(series.mean()), 4) if len(series) > 0 else None,
                    "std": round(float(series.std()), 4) if len(series) > 0 else None,
                    "min": round(float(series.min()), 4) if len(series) > 0 else None,
                    "max": round(float(series.max()), 4) if len(series) > 0 else None,
                    "trend": "upward" if len(series) >= 2 and series.iloc[-1] > series.iloc[0]
                    else "downward" if len(series) >= 2 and series.iloc[-1] < series.iloc[0] else "flat",
                    "missing": int(df[col].isnull().sum()),
                }

                outliers = 0
                if len(series) >= 2:
                    mean_v = col_stat["mean"]
                    std_v = col_stat["std"]
                    if std_v and std_v > 0:
                        outliers = int((abs(series - mean_v) > 2.5 * std_v).sum())
                col_stat["outlier_count"] = outliers
                result["summary"][col] = col_stat

            for i, col in enumerate(numeric_cols[:6]):
                plot_id = hashlib.md5(f"ts:{ds_id}:{col}".encode()).hexdigest()[:12]
                result["plots"].append({
                    "plot_id": plot_id,
                    "type": "line",
                    "title": f"{col} 时间序列趋势",
                    "description": f"时间序列折线图展示 {col} 的变化趋势（数据集: {ds_filename}）",
                    "data_source": col,
                    "x_key": "index",
                    "y_key": col,
                    "x_label": "时间点",
                    "y_label": col,
                    "source_dataset_id": ds_id,
                    "is_generated_from_real_data": True,
                })

        return result

    def _analyze_json_dataset(
        self, ds_id: str, ds_filename: str, ds_path: str, ds: dict
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "has_real_data": False,
            "summary": {},
            "feature_vectors": [],
            "sample_rows": [],
        }

        data = None
        if ds_path and os.path.isfile(ds_path):
            try:
                with open(ds_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"读取 JSON 失败 {ds_path}: {e}")

        if data is None:
            preview = ds.get("preview", [])
            if preview:
                result["has_real_data"] = True
                result["summary"] = {
                    "n_records": len(preview),
                    "top_keys": list(preview[0].keys()) if preview else [],
                }
                result["sample_rows"] = preview
            return result

        if isinstance(data, list) and len(data) > 0:
            result["has_real_data"] = True
            result["summary"] = {
                "n_records": len(data),
                "top_keys": list(data[0].keys()) if isinstance(data[0], dict) else ["(array_element)"],
            }
            result["sample_rows"] = data[:100]
        elif isinstance(data, dict):
            result["has_real_data"] = True
            result["summary"] = {
                "n_top_keys": len(data),
                "keys": list(data.keys())[:20],
            }
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0:
                    result["sample_rows"] = v[:100]
                    result["summary"]["array_key"] = k
                    break

        return result

    def _build_plot_specs(
        self, ds_id: str, ds_filename: str, numeric_cols: list, categorical_cols: list = None
    ) -> List[dict]:
        plots: List[dict] = []
        categorical_cols = categorical_cols or []

        if not numeric_cols:
            return plots

        for col in numeric_cols[:3]:
            plot_id = hashlib.md5(f"hist:{ds_id}:{col}".encode()).hexdigest()[:12]
            plots.append({
                "plot_id": plot_id,
                "type": "histogram",
                "title": f"{col} 数值分布直方图",
                "description": f"直方图展示 {col} 的分布特征（数据集: {ds_filename}）",
                "data_source": col,
                "x_key": col,
                "y_key": col,
                "x_label": col,
                "y_label": "频次",
                "source_dataset_id": ds_id,
                "is_generated_from_real_data": True,
                "chart_kind": "descriptive_stat",
            })

        if len(numeric_cols) >= 2:
            for i, c1 in enumerate(numeric_cols[:3]):
                for c2 in numeric_cols[i + 1:i + 2]:
                    if c2 not in numeric_cols:
                        continue
                    plot_id = hashlib.md5(f"scatter:{ds_id}:{c1}:{c2}".encode()).hexdigest()[:12]
                    plots.append({
                        "plot_id": plot_id,
                        "type": "scatter",
                        "title": f"{c1} vs {c2} 相关性散点图",
                        "description": f"散点图展示 {c1} 与 {c2} 的相关性（数据集: {ds_filename}）",
                        "data_source": f"{c1},{c2}",
                        "x_key": c1,
                        "y_key": c2,
                        "x_label": c1,
                        "y_label": c2,
                        "source_dataset_id": ds_id,
                        "is_generated_from_real_data": True,
                        "chart_kind": "descriptive_stat",
                    })

        if len(numeric_cols) >= 3:
            plot_id = hashlib.md5(f"heatmap:{ds_id}:corr".encode()).hexdigest()[:12]
            plots.append({
                "plot_id": plot_id,
                "type": "heatmap",
                "title": "数值特征相关性热力图",
                "description": f"热力图展示数值特征间的 Pearson 相关性矩阵（数据集: {ds_filename}）",
                "data_source": "correlation_matrix",
                "x_key": "columns",
                "y_key": "columns",
                "x_label": "特征",
                "y_label": "特征",
                "source_dataset_id": ds_id,
                "is_generated_from_real_data": True,
                "chart_kind": "descriptive_stat",
            })

        if categorical_cols:
            for col in categorical_cols[:2]:
                plot_id = hashlib.md5(f"bar:{ds_id}:{col}".encode()).hexdigest()[:12]
                plots.append({
                    "plot_id": plot_id,
                    "type": "bar",
                    "title": f"{col} 类别分布柱状图",
                    "description": f"柱状图展示 {col} 各类别的频次分布（数据集: {ds_filename}）",
                    "data_source": col,
                    "x_key": col,
                    "y_key": col,
                    "x_label": col,
                    "y_label": "频次",
                    "source_dataset_id": ds_id,
                    "is_generated_from_real_data": True,
                    "chart_kind": "descriptive_stat",
                })

        return plots

    def _build_summary_from_stats(
        self, columns: list, dtypes: dict, n_rows: int, statistics: dict, ds: dict
    ) -> dict:
        summary = {"n_rows": n_rows, "n_columns": len(columns), "source": "precomputed_stats"}
        for col in columns:
            if col in statistics:
                summary[col] = statistics[col]
        summary["missing_count"] = ds.get("missing_count", 0)
        summary["missing_rate"] = ds.get("missing_rate", 0)
        return summary

    @staticmethod
    def _compute_pearson_correlation(x: list, y: list) -> Optional[float]:
        if not x or not y or len(x) < 2:
            return None
        pairs = [(float(xv), float(yv)) for xv, yv in zip(x, y)
                 if xv is not None and yv is not None
                 and not (isinstance(xv, float) and math.isnan(xv))
                 and not (isinstance(yv, float) and math.isnan(yv))]
        if len(pairs) < 2:
            return None
        n = len(pairs)
        mean_x = sum(p[0] for p in pairs) / n
        mean_y = sum(p[1] for p in pairs) / n
        cov = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs) / n
        std_x = (sum((p[0] - mean_x) ** 2 for p in pairs) / n) ** 0.5
        std_y = (sum((p[1] - mean_y) ** 2 for p in pairs) / n) ** 0.5
        if std_x == 0 or std_y == 0:
            return 0.0
        return round(cov / (std_x * std_y), 4)

    def _build_preliminary_result(
        self,
        summary_stats: dict,
        feature_vectors: list,
        correlations: list,
        anomalies: list,
        hypothesis: str,
    ) -> Dict[str, Any]:
        result = {
            "is_analyzable": bool(summary_stats),
            "data_quality": "good" if len(anomalies) < 10 else "needs_attention",
            "recommendations": [],
            "data_source": "real_data" if summary_stats else "no_data",
        }

        if not summary_stats:
            result["recommendations"].append("缺少真实结构化数据，无法进行统计分析。建议上传 CSV、Excel 或 JSON 数据集")
        else:
            result["recommendations"].append("已基于真实数据完成初步统计分析")

        if feature_vectors:
            total_features = sum(len(fv.get("features", [])) for fv in feature_vectors)
            result["recommendations"].append(
                f"检测到 {len(feature_vectors)} 个数据集含 {total_features} 个数值特征，可用于建模"
            )

        if correlations:
            high_corrs = [c for c in correlations if c.get("pearson_r") is not None and abs(c["pearson_r"]) > 0.7]
            if high_corrs:
                result["recommendations"].append(
                    f"发现 {len(high_corrs)} 对强相关特征，建议考虑降维或特征选择"
                )

        if anomalies:
            result["recommendations"].append(
                f"检测到 {len(anomalies)} 个异常数据点（超出 2.5σ），建议在分析前进行数据清洗"
            )

        if hypothesis:
            result["hypothesis_feedback"] = f"初步分析已基于真实数据完成，可针对假设「{hypothesis[:100]}」进行验证"

        return result

    def _build_empty_result(self, hypothesis: str) -> Dict[str, Any]:
        return {
            "is_analyzable": False,
            "data_quality": "no_data",
            "recommendations": [
                "缺少真实结构化数据，无法进行统计分析",
                "建议上传 CSV、Excel 或 JSON 数据集以启用数据驱动分析",
            ],
            "data_source": "no_data",
            "hypothesis_feedback": f"缺少真实数据，无法对假设「{hypothesis[:100]}」进行数据驱动验证",
        }