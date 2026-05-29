import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class DataJuicerLiteSkill(BaseSkill):
    name = "data_juicer_lite"
    description = "轻量级数据质量分析，不做破坏性修改，仅报告质量"
    source_reference = "data_juicer_lite"
    source_version = "1.1.0"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        file_paths: List[str] = input_data.get("file_paths", [])
        file_metas: List[dict] = input_data.get("file_metas", [])
        missing_strategy = input_data.get("missing_strategy", "report")
        outlier_method = input_data.get("outlier_method", "iqr")
        outlier_threshold = input_data.get("outlier_threshold", 1.5)

        if not file_metas and not file_paths:
            result.success = False
            result.errors.append("缺少 file_metas 或 file_paths")
            return result

        file_reports: List[dict] = []
        total_fields = 0
        total_missing = 0
        total_rows = 0
        total_duplicates = 0
        total_outliers = 0

        for meta in file_metas:
            data_type = meta.get("data_type", "tabular")
            file_path = meta.get("file_path", "unknown")
            filename = meta.get("filename", Path(file_path).name if file_path else "unknown")

            try:
                if data_type == "tabular":
                    tr = self._analyze_tabular_quality(meta, missing_strategy)
                    tr["file_path"] = file_path
                    tr["filename"] = filename
                    tr["data_type"] = data_type
                    file_reports.append(tr)
                    total_fields += tr.get("total_fields", 0)
                    total_missing += tr.get("missing_cells", 0)
                    total_rows += tr.get("n_rows", 0)
                    total_duplicates += tr.get("duplicate_rows", 0)
                    total_outliers += tr.get("outlier_count", 0)

                elif data_type == "image":
                    ir = self._analyze_image_quality(meta)
                    ir["file_path"] = file_path
                    ir["filename"] = filename
                    ir["data_type"] = data_type
                    file_reports.append(ir)

                elif data_type in ("time_series", "timeseries"):
                    tsr = self._analyze_timeseries_quality(meta, missing_strategy)
                    tsr["file_path"] = file_path
                    tsr["filename"] = filename
                    tsr["data_type"] = data_type
                    file_reports.append(tsr)

                elif data_type in ("json",):
                    jr = self._analyze_json_quality(meta)
                    jr["file_path"] = file_path
                    jr["filename"] = filename
                    jr["data_type"] = data_type
                    file_reports.append(jr)

                else:
                    file_reports.append({
                        "file_path": file_path,
                        "filename": filename,
                        "data_type": data_type,
                        "warning": f"不支持的数据类型: {data_type}",
                        "quality_score": 0.5,
                        "issues": [],
                    })
                    result.warnings.append(f"不支持的数据类型 {data_type}，仅记录基本信息")

            except Exception as e:
                logger.warning(f"分析文件 {filename} 质量失败: {e}")
                file_reports.append({
                    "file_path": file_path,
                    "filename": filename,
                    "data_type": data_type,
                    "error": str(e),
                    "quality_score": 0.0,
                    "issues": [f"分析失败: {str(e)[:200]}"],
                })
                result.warnings.append(f"文件 {filename} 质量分析失败: {e}")

        overall_score = self._compute_overall_score(
            file_reports, total_fields, total_missing, total_rows, total_duplicates, total_outliers
        )
        recommendations = self._generate_recommendations(
            file_reports, overall_score, total_missing, total_duplicates, total_outliers
        )

        quality_report = {
            "overall_score": overall_score,
            "missing_rate": round(total_missing / max(total_fields, 1), 4),
            "total_missing": total_missing,
            "total_rows": total_rows,
            "total_duplicates": total_duplicates,
            "total_outliers": total_outliers,
            "file_count": len(file_reports),
            "duplicate_summary": {
                "total_duplicate_rows": total_duplicates,
                "total_rows": total_rows,
                "duplicate_rate": round(total_duplicates / max(total_rows, 1), 4),
            },
            "outlier_summary": {
                "total_outliers": total_outliers,
                "detection_method": outlier_method,
                "threshold": outlier_threshold if outlier_method == "iqr" else None,
            },
            "numeric_statistics": [],
            "class_distribution": {},
            "image_metadata": [],
            "time_series_metadata": [],
            "recommendations": recommendations,
        }

        for r in file_reports:
            if r.get("data_type") == "tabular":
                if r.get("numeric_statistics_summary"):
                    quality_report["numeric_statistics"].append({
                        "filename": r.get("filename"),
                        "stats": r["numeric_statistics_summary"],
                    })
                if r.get("class_distribution"):
                    quality_report["class_distribution"][r.get("filename", "")] = r["class_distribution"]
            elif r.get("data_type") == "image":
                quality_report["image_metadata"].append({
                    "filename": r.get("filename"),
                    "image_count": r.get("image_count", 0),
                    "dimensions": r.get("dimensions", {}),
                    "channels": r.get("channels", 0),
                    "file_format": r.get("file_format", ""),
                    "quality_score": r.get("quality_score", 0),
                })
            elif r.get("data_type") in ("time_series", "timeseries"):
                quality_report["time_series_metadata"].append({
                    "filename": r.get("filename"),
                    "total_observations": r.get("total_observations", 0),
                    "missing_rate": r.get("missing_rate", 0),
                    "has_time_column": r.get("has_time_column", False),
                    "time_range": r.get("time_range", ""),
                    "sampling_interval": r.get("sampling_interval", ""),
                    "quality_score": r.get("quality_score", 0),
                })

        result.data = {
            "quality_report": quality_report,
            "overall_score": overall_score,
            "file_reports": file_reports,
            "recommendations": recommendations,
            "cleaned_file_paths": [],
        }

        return result

    @staticmethod
    def _analyze_tabular_quality(meta: dict, missing_strategy: str) -> dict:
        columns: List[str] = meta.get("columns", [])
        dtypes: Dict[str, str] = meta.get("dtypes", {})
        preview: List[dict] = meta.get("preview", [])
        n_rows = meta.get("n_rows", 0)
        n_columns = meta.get("n_columns", len(columns))
        statistics = meta.get("statistics", {})

        total_fields = n_rows * max(n_columns, 1)
        missing_cells = meta.get("missing_count", 0)
        missing_rate = round(missing_cells / max(total_fields, 1), 4)

        categorical_field_count = 0
        numeric_field_count = 0
        for col, dt in dtypes.items():
            dt_lower = (dt or "").lower()
            if any(k in dt_lower for k in ("int", "float", "num", "real", "double")):
                numeric_field_count += 1
            else:
                categorical_field_count += 1

        duplicate_rows = 0
        if preview and columns:
            seen = set()
            for row in preview:
                key = json.dumps({c: row.get(c) for c in columns}, default=str, ensure_ascii=False)
                if key in seen:
                    duplicate_rows += 1
                else:
                    seen.add(key)

        outlier_count = 0
        outlier_fields: List[str] = []
        numeric_stats = statistics if statistics else {}
        if not numeric_stats and preview:
            basic = DataJuicerLiteSkill._compute_basic_stats_from_preview(preview, columns, dtypes)
            numeric_stats = basic.get("numeric_statistics", {})

        for col, stats in numeric_stats.items():
            if not isinstance(stats, dict):
                continue
            q1 = stats.get("q1") or stats.get("min")
            q3 = stats.get("q3") or stats.get("max")
            if q1 is None or q3 is None:
                continue
            iqr = q3 - q1
            if iqr <= 0:
                continue
            lo = q1 - 1.5 * iqr
            hi = q3 + 1.5 * iqr
            if stats.get("min", lo) < lo or stats.get("max", hi) > hi:
                outlier_fields.append(col)
                outlier_count += abs(int(stats.get("missing", 0)) - int(stats.get("count", 1)))

        class_dist = {}
        for col in columns:
            col_stats = statistics.get(col, {})
            if isinstance(col_stats, dict) and col_stats.get("top_values"):
                class_dist[col] = col_stats["top_values"]
            else:
                top_vals = (col_stats.get("top") if isinstance(col_stats, dict) else None)
                if top_vals:
                    class_dist[col] = {item["value"]: item["count"] for item in top_vals[:10]}

        quality_score = 1.0
        issues: List[str] = []
        if missing_rate > 0.3:
            quality_score -= 0.4
            issues.append(f"缺失率偏高 ({missing_rate:.1%})")
        elif missing_rate > 0.1:
            quality_score -= 0.2
            issues.append(f"存在较多缺失 ({missing_rate:.1%})")
        if duplicate_rows > 0 and n_rows > 0:
            if duplicate_rows / n_rows > 0.3:
                quality_score -= 0.3
                issues.append(f"重复行比例偏高 ({duplicate_rows / n_rows:.1%})")
        if outlier_fields:
            issues.append(f"存在离群值的字段: {', '.join(outlier_fields[:5])}")

        return {
            "missing_cells": missing_cells,
            "missing_rate": round(missing_rate, 4),
            "total_fields": total_fields,
            "n_rows": n_rows,
            "n_columns": n_columns,
            "duplicate_rows": duplicate_rows,
            "duplicate_rate": round(duplicate_rows / max(n_rows, 1), 4),
            "outlier_count": outlier_count,
            "outlier_fields": outlier_fields[:10],
            "numeric_field_count": numeric_field_count,
            "categorical_field_count": categorical_field_count,
            "class_distribution": class_dist,
            "numeric_statistics_summary": {
                k: {"mean": v.get("mean"), "std": v.get("std"), "min": v.get("min"), "max": v.get("max")}
                for k, v in list(numeric_stats.items())[:20]
            },
            "categorical_top_categories": {
                k: (v.get("top", [])[:5] if isinstance(v, dict) else [])
                for k, v in list(numeric_stats.items())[:10]
                if isinstance(v, dict) and v.get("top")
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
        n_images = meta.get("n_images") or meta.get("total_images") or meta.get("image_count") or 0

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
        n_samples = meta.get("n_samples", n_rows)
        missing_count = meta.get("missing_count", 0)
        series_summary = meta.get("time_series_summary", {})
        statistics = meta.get("statistics", {})

        missing_obs = missing_count
        total_obs = n_samples or n_rows

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
        if total_obs > 0 and missing_obs / total_obs > 0.3:
            issues.append(f"缺失观测比 {missing_obs / total_obs:.1%}")
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
    def _analyze_json_quality(meta: dict) -> dict:
        record_count = meta.get("record_count", meta.get("n_rows", 0))
        top_level_keys = meta.get("top_level_keys", meta.get("columns", []))
        preview = meta.get("preview", [])

        quality_score = 0.7
        issues: List[str] = []
        if record_count < 5:
            issues.append(f"记录数过少 ({record_count})")
            quality_score -= 0.2
        if not top_level_keys:
            issues.append("未检测到顶层字段")
            quality_score -= 0.3

        return {
            "record_count": record_count,
            "field_count": len(top_level_keys),
            "fields": top_level_keys[:30],
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
                recs.append(f"[{r.get('filename', 'unknown')}] {issue}")
        if not recs:
            recs.append("数据质量良好，可直接用于分析")
        return recs