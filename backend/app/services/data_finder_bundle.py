"""Analysis-Ready Bundle — 可下载分析包"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.core.data_cleaning import infer_csv_schema

CHINA_TZ = timezone(timedelta(hours=8))


def _bundle_dir(project_dir: str) -> str:
    path = os.path.join(project_dir, "bundle")
    os.makedirs(path, exist_ok=True)
    return path


def build_analysis_bundle(
    project_id: str,
    project_dir: str,
    results: Dict[str, Any],
    *,
    coverage_report: Optional[Dict[str, Any]] = None,
    cleaning_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """写入 Analysis-Ready Bundle 目录并打包 zip。"""
    bundle_path = _bundle_dir(project_dir)
    merged = results.get("merged") or {}

    csv_src = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
    if not csv_src or not os.path.exists(csv_src):
        return {"bundle_path": bundle_path, "ready": False, "reason": "无合并 CSV"}

    dest_csv = os.path.join(bundle_path, "merged.csv")
    shutil.copy2(csv_src, dest_csv)

    schema = infer_csv_schema(dest_csv)
    schema_path = os.path.join(bundle_path, "schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    prov_path = os.path.join(bundle_path, "provenance.jsonl")
    with open(prov_path, "w", encoding="utf-8") as f:
        for rec in results.get("provenance") or []:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        for rec in results.get("row_provenance") or []:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    quality_report = {
        "cleaning": cleaning_report or merged.get("cleaning_report") or {},
        "merge_id": merged.get("merge_id"),
        "row_count": merged.get("row_count"),
        "columns": merged.get("columns"),
        "source_csv": merged.get("merged_csv_path"),
        "cleaned_csv": merged.get("cleaned_csv_path"),
    }
    quality_path = os.path.join(bundle_path, "quality_report.json")
    with open(quality_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, ensure_ascii=False, indent=2)

    if coverage_report:
        cov_path = os.path.join(bundle_path, "coverage_report.json")
        with open(cov_path, "w", encoding="utf-8") as f:
            json.dump(coverage_report, f, ensure_ascii=False, indent=2)

    readme = _build_readme(project_id, results, coverage_report, cleaning_report)
    readme_path = os.path.join(bundle_path, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)

    zip_path = os.path.join(project_dir, "analysis_bundle.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("merged.csv", "schema.json", "provenance.jsonl", "quality_report.json", "README.md"):
            fp = os.path.join(bundle_path, name)
            if os.path.exists(fp):
                zf.write(fp, arcname=name)
        if coverage_report:
            cov_fp = os.path.join(bundle_path, "coverage_report.json")
            if os.path.exists(cov_fp):
                zf.write(cov_fp, arcname="coverage_report.json")

    return {
        "bundle_path": bundle_path,
        "bundle_zip_path": zip_path,
        "ready": True,
        "files": [
            "merged.csv",
            "schema.json",
            "provenance.jsonl",
            "quality_report.json",
            "coverage_report.json",
            "README.md",
        ],
        "generated_at": datetime.now(CHINA_TZ).isoformat(),
    }


def _build_readme(
    project_id: str,
    results: Dict[str, Any],
    coverage: Optional[Dict[str, Any]],
    cleaning: Optional[Dict[str, Any]],
) -> str:
    merged = results.get("merged") or {}
    lines = [
        f"# Analysis-Ready Bundle — Project {project_id}",
        "",
        f"生成时间: {datetime.now(CHINA_TZ).isoformat()}",
        "",
        "## 文件说明",
        "- `merged.csv`: 合并（及可选清洗后）的多源表格，含 `_provenance_*` 与 `_cleaning_action`",
        "- `schema.json`: 列类型与非空统计",
        "- `provenance.jsonl`: 行级/表级来源记录",
        "- `quality_report.json`: 清洗前后与 merge 元信息",
        "- `coverage_report.json`: 子领域数据发现完备性",
        "",
        "## 合并摘要",
        f"- 行数: {merged.get('row_count', '—')}",
        f"- merge_id: {merged.get('merge_id', '—')}",
        f"- 清洗: {'是' if merged.get('cleaned_csv_path') else '否'}",
        "",
    ]
    if coverage:
        lines.extend([
            "## 完备性",
            f"- 得分: {coverage.get('completeness_score', '—')}/100",
            f"- 缺口: {', '.join(coverage.get('gaps') or []) or '无'}",
            "",
        ])
    if cleaning:
        lines.extend([
            "## 清洗",
            f"- 行 {cleaning.get('rows_before')} → {cleaning.get('rows_after')}",
            f"- 缺失单元 {cleaning.get('missing_cells_before')} → {cleaning.get('missing_cells_after')}",
            "",
        ])
    lines.append("## 方法")
    lines.append("表格来自 PDF 抽取 + 字段对齐 + 纵向合并；清洗为去重与中位数/unknown 填充。")
    return "\n".join(lines)
