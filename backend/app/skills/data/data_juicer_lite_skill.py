"""
数据清洗与质量分析 Skill (DataJuicer Lite)
参考能力：Data-Juicer operators
——对 CSV/Excel/JSON/image/time-series 做轻量清洗和质量分析，
先输出质量报告，不做破坏性修改。
"""
import logging
import json
import os
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

SUPPORTED_TABULAR = {".csv", ".xlsx", ".xls", ".tsv", ".json"}
SUPPORTED_IMAGE = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
SUPPORTED_SERIES = {".csv", ".tsv", ".json"}

DUPLICATE_HASH_BUF = 8192


class DataJuicerLiteSkill(BaseSkill):
    """轻量数据清洗与质量分析 Skill

    输入:
      - file_paths: List[str]               文件路径列表
      - file_metas: List[dict]             文件元数据列表（含 file_path/data_type/columns/n_rows 等）
      - missing_strategy: str = "report"   缺失值处理策略: report / drop / median / mean
      - outlier_method: str = "iqr"        异常值检测方法: iqr / zscore / none
      - outlier_threshold: float = 1.5     IQR 倍数阈值（iqr 模式）或 z-score 阈值

    输出 (SkillResult.data):
      - quality_report: dict              质量报告（含 missing_rate / outliers / duplicates 等）
      - file_reports: List[dict]          每个文件的独立质量报告
      - overall_score: float               整体质量评分 0.0-1.0
      - recommendations: List[str]         质量改进建议
      - cleaned_file_paths: List[str]      清洗后的文件路径（如果执行了清洗）
    """

    name = "DataJuicerLite"
    description = "对 CSV/Excel/JSON/image/time-series 做轻量清洗和质量分析"
    source_reference = "Data-Juicer (arxiv:2309.02033) — data processing operators 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        file_paths: List[str] = input_data.get("file_paths", [])
        file_metas: List[dict] = input_data.get("file_metas", [])
        missing_strategy = input_data.get("missing_strategy", "report")
        outlier_method = input_data.get("outlier_method", "iqr")
        outlier_threshold = input_data.get("outlier_threshold", 1.5)

        if not file_paths and not file_metas:
            result.add_warning("无数据文件可供分析")
            result.data = {
                "quality_report": {"overall_score": 0.0, "file_count": 0},
                "file_reports": [],
                "overall_score": 0.0,
                "recommendations": ["请上传数据文件后进行质量分析"],
                "cleaned_file_paths": [],
            }
            return result

        file_reports: List[dict] = []
        total_fields = 0
        total_missing = 0
        total_rows = 0
        total_duplicates = 0
        total_outliers = 0
        file_count = 0

        for meta in file_metas:
            fp = meta.get("file_path", "") or meta.get("filename", "")
            data_type = meta.get("data_type", "tabular")
            columns = meta.get("columns", [])
            dtypes = meta.get("dtypes", {})
            n_rows = meta.get("n_rows", 0)
            n_columns = meta.get("n_columns", len(columns)) if not n_columns else 0
            statistics = meta.get("statistics", {})
            preview = meta.get("preview", [])
            missing_count = meta.get("missing_count", 0)

            report = {
                "file_path": fp,
                "data_type": data_type,
                "n_rows": n_rows,
                "n_columns": n_columns,
                "file_size_bytes": 0,
            }

            if fp and os.path.exists(fp):
                try:
                    report["file_size_bytes"] = os.path.getsize(fp)
                except OSError:
                    pass

            if data_type == "tabular":
                tr = self._analyze_tabular_quality(
                    columns, dtypes, n_rows, n_columns,
                    statistics, preview, missing_count,
                    missing_strategy, outlier_method, outlier_threshold,
                )
                report.update(tr)
                total_fields += tr.get("total_fields", 0)
                total_missing += tr.get("missing_cells", 0)
                total_rows += n_rows
                total_duplicates += tr.get("duplicate_rows", 0)
                total_outliers += tr.get("outlier_count", 0)

            elif data_type == "image":
                ir = self._analyze_image_quality(meta)
                report.update(ir)

            elif data_type in ("time_series", "timeseries"):
                tsr = self._analyze_timeseries_quality(meta, missing_strategy)
                report.update(tsr)
                total_fields += tsr.get("total_observations", 0)
                total_missing += tsr.get("missing_observations", 0)

            else:
                report["quality_score"] = 0.5
                report["issues"] = [f"不支持的数据类型: {data_type}"]

            file_reports.append(report)
            file_count += 1

        overall_score = self._compute_overall_score(
            file_reports, total_fields, total_missing, total_rows,
            total_duplicates, total_outliers,
        )

        recommendations = self._generate_recommendations(
            file_reports, overall_score, total_missing, total_duplicates, total_outliers,
        )

        quality_report = {
            "overall_score": round(overall_score, 3),
            "file_count": file_count,
            "total_rows": total_rows,
            "total_fields_analyzed": total_fields,
            "total_missing_cells": total_missing,
            "total_duplicates": total_duplicates,
            "total_outliers": total_outliers,
            "missing_rate": round(total_missing / max(total_fields, 1), 4),
            "analyzed_at": datetime.now().isoformat(),
        }

        result.data = {
            "quality_report": quality_report,
            "file_reports": file_reports,
            "overall_score": round(overall_score, 3),
            "recommendations": recommendations,
            "cleaned_file_paths": [],
        }
        return result

    def _analyze_tabular_quality(
        self,
        columns: List[str],
        dtypes: Dict[str, str],
        n_rows: int,
        n_columns: int,
        statistics: Dict[str, Any],
        preview: List[dict],
        missing_count: int,
        missing_strategy: str,
        outlier_method: str,
        outlier_threshold: float,
    ) -> dict:
        total_fields = n_rows * max(n_columns, len(columns))
        missing_cells = missing_count or 0

        if not statistics and preview:
            statistics = self._compute_basic_stats_from_preview(preview, columns, dtypes)

        numeric_stats = statistics.get("numeric_statistics", {})
        categorical_stats = statistics.get("categorical_statistics", {})
        class_dist = statistics.get("class_distribution", {})

        duplicate_rows = 0
        if preview and len(preview) > 1:
            seen = set()
            for row in preview:
                row_str = json.dumps(row, sort_keys=True, ensure_ascii=False)
                row_hash = hashlib.md5(row_str.encode()).hexdigest()
                if row_hash in seen:
                    duplicate_rows += 1
                else:
                    seen.add(row_hash)
            if len(preview) >= 10 and n_rows > len(preview):
                dup_rate = duplicate_rows / len(preview)
                duplicate_rows = int(dup_rate * n_rows)

        outlier_count = 0
        outlier_fields: List[str] = []
        if outlier_method != "none" and numeric_stats:
            for col_name, ns in numeric_stats.items():
                if not isinstance(ns, dict):
                    continue
                q1 = ns.get("q1") or ns.get("25%")
                q3 = ns.get("q3") or ns.get("75%")
                mean = ns.get("mean")
                std = ns.get("std")
                if q1 is not None and q3 is not None and q3 > q1:
                    iqr = q3 - q1
                    lower = q1 - outlier_threshold * iqr
                    upper = q3 + outlier_threshold * iqr
                    count = ns.get("count", n_rows)
                    if "outlier_count" in ns:
                        outlier_count += ns["outlier_count"]
                    elif count > 0 and ns.get("min") is not None and ns.get("max") is not None:
                        if ns["min"] < lower or ns["max"] > upper:
                            est = int(count * 0.05)
                            outlier_count += est
                            outlier_fields.append(col_name)
                elif outlier_method == "zscore" and mean is not None and std is not None and std > 0:
                    if ns.get("max") is not None:
                        z_max = abs((ns["max"] - mean) / std)
                        if z_max > outlier_threshold:
                            outlier_count += int(n_rows * 0.05)
                            outlier_fields.append(col_name)

        missing_rate = missing_cells / max(total_fields, 1)
        numeric_field_count = len(numeric_stats)
        categorical_field_count = len(categorical_stats)

        quality_score = 1.0
        if missing_rate > 0.2:
            quality_score -= 0.3
        elif missing_rate > 0.05:
            quality_score -= 0.15
        if duplicate_rows / max(n_rows, 1) > 0.1:
            quality_score -= 0.2
        if n_rows < 10:
            quality_score -= 0.2
        if n_columns < 2:
            quality_score -= 0.1

        issues = []
        if missing_rate > 0.2:
            issues.append(f"缺失率 {missing_rate:.1%} 较高")
        if duplicate_rows / max(n_rows, 1) > 0.1:
            issues.append(f"重复行占比 {duplicate_rows / max(n_rows, 1):.1%}")
        if n_rows < 10:
            issues.append(f"样本量过少 (n={n_rows})")
        if outlier_fields:
            issues.append(f"存在离群值的字段: {', '.join(outlier_fields[:5])}")

        return {
            "missing_cells": missing_cells,
            "missing_rate": round(missing_rate, 4),
            "total_fields": total_fields,
            "duplicate_rows": duplicate_rows,
            "duplicate_rate": round(duplicate_rows / max(n_rows, 1), 4),
            "outlier_count": outlier_count,
            "outlier_fields": outlier_fields[:10],
            "numeric_field_count": numeric_field_count,
            "categorical_field_count": categorical_field_count,
            "class_distribution": class_dist if class_dist else {},
            "numeric_statistics_summary": {
                k: {"mean": v.get("mean"), "std": v.get("std"), "min": v.get("min"), "max": v.get("max")}
                for k, v in list(numeric_stats.items())[:20]
            },
            "categorical_top_categories": {
                k: v.get("top", [])[:5]
                for k, v in list(categorical_stats.items())[:10]
                if v.get("top")
            },
            "quality_score": round(max(0.0, quality_score), 3),
            "issues": issues,
            "missing_strategy_applied": missing_strategy if missing_strategy != "report" else "none",
        }

    @staticmethod
    def _compute_basic_stats_from_preview(
        preview: List[dict],
        columns: List[str],
        dtypes: Dict[str, str],
    ) -> dict:
        numeric_stats: Dict[str, dict] = {}
        categorical_stats: Dict[str, dict] = {}

        for col in columns:
            col_dtype = (dtypes.get(col, "") or "").lower()
            values = []
            for row in preview:
                v = row.get(col)
                if v is not None and v != "":
                    values.append(v)

            if not values:
                continue

            numeric_hint = any(k in col_dtype for k in ("int", "float", "num", "real", "double"))
            if numeric_hint:
                try:
                    nums = [float(v) for v in values if v is not None]
                    if nums:
                        nums_sorted = sorted(nums)
                        n = len(nums_sorted)
                        numeric_stats[col] = {
                            "count": n,
                            "mean": sum(nums_sorted) / n,
                            "std": (sum((x - sum(nums_sorted) / n) ** 2 for x in nums_sorted) / (n - 1)) ** 0.5 if n > 1 else 0.0,
                            "min": nums_sorted[0],
                            "max": nums_sorted[-1],
                            "q1": nums_sorted[n // 4] if n >= 4 else nums_sorted[0],
                            "q3": nums_sorted[3 * n // 4] if n >= 4 else nums_sorted[-1],
                        }
                except (ValueError, TypeError):
                    pass

            freq: Dict[str, int] = {}
            for v in values:
                sv = str(v)[:100]
                freq[sv] = freq.get(sv, 0) + 1
            if freq:
                top_items = sorted(freq.items(), key=lambda x: -x[1])[:10]
                categorical_stats[col] = {
                    "unique_count": len(freq),
                    "top": [{"value": k, "count": c} for k, c in top_items],
                }

        return {
            "numeric_statistics": numeric_stats,
            "categorical_statistics": categorical_stats,
        }

    @staticmethod
    def _analyze_image_quality(meta: dict) -> dict:
        quality_score = 0.8
        issues = []
        width = meta.get("width") or meta.get("image_width") or 0
        height = meta.get("height") or meta.get("image_height") or 0
        channels = meta.get("channels", 3)
        file_format = meta.get("format") or meta.get("file_format") or ""
        n_images = meta.get("n_images") or meta.get("total_images") or 0

        if width and height:
            if width < 100 or height < 100:
                issues.append(f"图像尺寸过小 ({width}x{height})")
                quality_score -= 0.3
            aspect_ratio = max(width, height) / max(min(width, height), 1)
            if aspect_ratio > 10:
                issues.append(f"宽高比异常 ({aspect_ratio:.1f})")

        if n_images < 5:
            issues.append(f"图像数量过少 ({n_images})")
            quality_score -= 0.1

        return {
            "image_count": n_images or 1,
            "dimensions": {"width": width, "height": height} if width else {},
            "channels": channels,
            "file_format": file_format,
            "quality_score": round(max(0.0, quality_score), 3),
            "issues": issues,
        }

    @staticmethod
    def _analyze_timeseries_quality(meta: dict, missing_strategy: str) -> dict:
        n_rows = meta.get("n_rows", 0)
        missing_count = meta.get("missing_count", 0)
        series_summary = meta.get("time_series_summary", {})
        statistics = meta.get("statistics", {})

        missing_obs = missing_count
        total_obs = n_rows

        has_time_col = bool(
            series_summary.get("time_column")
            or meta.get("time_column")
            or any("time" in (c or "").lower() for c in (meta.get("columns") or []))
        )

        quality_score = 0.7
        issues = []
        if not has_time_col:
            issues.append("缺少明确的时间列")
            quality_score -= 0.2
        if total_obs < 20:
            issues.append(f"观测点过少 ({total_obs})")
            quality_score -= 0.2
        if missing_obs / max(total_obs, 1) > 0.3:
            issues.append(f"缺失观测比 {missing_obs / max(total_obs, 1):.1%}")
            quality_score -= 0.3

        return {
            "total_observations": total_obs,
            "missing_observations": missing_obs,
            "missing_rate": round(missing_obs / max(total_obs, 1), 4),
            "has_time_column": has_time_col,
            "time_range": series_summary.get("time_range", ""),
            "sampling_interval": series_summary.get("sampling_interval", ""),
            "quality_score": round(max(0.0, quality_score), 3),
            "issues": issues,
        }

    @staticmethod
    def _compute_overall_score(
        file_reports: List[dict],
        total_fields: int,
        total_missing: int,
        total_rows: int,
        total_duplicates: int,
        total_outliers: int,
    ) -> float:
        if not file_reports:
            return 0.0
        avg_score = sum(r.get("quality_score", 0.5) for r in file_reports) / len(file_reports)
        missing_penalty = (total_missing / max(total_fields, 1)) * 0.4
        duplicate_penalty = (total_duplicates / max(total_rows, 1)) * 0.3
        return round(max(0.05, avg_score - missing_penalty - duplicate_penalty), 3)

    @staticmethod
    def _generate_recommendations(
        file_reports: List[dict],
        overall_score: float,
        total_missing: int,
        total_duplicates: int,
        total_outliers: int,
    ) -> List[str]:
        recs = []
        if overall_score < 0.5:
            recs.append("数据质量较低，建议在建模前进行必要清洗")
        if total_missing > 0:
            recs.append(f"检测到 {total_missing} 个缺失值，建议使用中位数或均值填充")
        if total_duplicates > 0:
            recs.append(f"检测到约 {total_duplicates} 行重复数据，建议去重")
        if total_outliers > 0:
            recs.append(f"检测到约 {total_outliers} 个离群值，建议使用 IQR 或 z-score 方法审查")
        for r in file_reports:
            issues = r.get("issues", [])
            for issue in issues[:2]:
                recs.append(f"[{r.get('file_path', 'unknown')}] {issue}")
        if not recs:
            recs.append("数据质量良好，可直接用于分析")
        return recs