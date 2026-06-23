"""Analysis-Ready Bundle — 可下载分析包"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.core.data_cleaning import infer_csv_schema
from app.schemas.data_integration import build_assets_index

CHINA_TZ = timezone(timedelta(hours=8))

BUNDLE_CORE_FILES = (
    "merged.csv",
    "data_spec.json",
    "schema.json",
    "assets_index.json",
    "provenance.jsonl",
    "quality_report.json",
    "README.md",
)


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

    data_spec = results.get("data_spec") or (results.get("data_requirements") or {}).get("data_spec") or {}
    spec_path = os.path.join(bundle_path, "data_spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(data_spec, f, ensure_ascii=False, indent=2)

    schema = infer_csv_schema(dest_csv)
    alignments = results.get("alignments") or []
    if alignments:
        schema["alignments"] = alignments
        schema["merge_strategy"] = alignments[0].get("merge_strategy")
        schema["join_keys"] = alignments[0].get("join_keys", [])
    schema_path = os.path.join(bundle_path, "schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    assets = results.get("assets_index") or build_assets_index(results)
    assets_path = os.path.join(bundle_path, "assets_index.json")
    with open(assets_path, "w", encoding="utf-8") as f:
        json.dump(assets, f, ensure_ascii=False, indent=2)

    prov_path = os.path.join(bundle_path, "provenance.jsonl")
    with open(prov_path, "w", encoding="utf-8") as f:
        for rec in results.get("provenance") or []:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        for rec in results.get("row_provenance") or []:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    figure_manifest_path = os.path.join(bundle_path, "figure_manifest.jsonl")
    figure_count = 0
    with open(figure_manifest_path, "w", encoding="utf-8") as f:
        for fig in results.get("figures") or []:
            manifest = fig.get("extraction_manifest") or {}
            if manifest:
                f.write(json.dumps(manifest, ensure_ascii=False) + "\n")
                figure_count += 1

    text_facts_path = os.path.join(bundle_path, "text_facts.jsonl")
    text_facts_count = 0
    with open(text_facts_path, "w", encoding="utf-8") as f:
        for fact in results.get("text_facts") or []:
            f.write(json.dumps(fact, ensure_ascii=False) + "\n")
            text_facts_count += 1

    quality_report = {
        "cleaning": cleaning_report or merged.get("cleaning_report") or {},
        "merge_id": merged.get("merge_id"),
        "row_count": merged.get("row_count"),
        "columns": merged.get("columns"),
        "source_csv": merged.get("merged_csv_path"),
        "cleaned_csv": merged.get("cleaned_csv_path"),
        "figure_manifest_count": figure_count,
        "text_facts_count": text_facts_count,
    }
    quality_path = os.path.join(bundle_path, "quality_report.json")
    with open(quality_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, ensure_ascii=False, indent=2)

    if coverage_report:
        cov_path = os.path.join(bundle_path, "coverage_report.json")
        with open(cov_path, "w", encoding="utf-8") as f:
            json.dump(coverage_report, f, ensure_ascii=False, indent=2)

    readme = _build_readme(project_id, results, coverage_report, cleaning_report, figure_count)
    readme_path = os.path.join(bundle_path, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)

    zip_names = list(BUNDLE_CORE_FILES)
    if figure_count > 0:
        zip_names.append("figure_manifest.jsonl")
    if text_facts_count > 0:
        zip_names.append("text_facts.jsonl")
    if coverage_report:
        zip_names.append("coverage_report.json")

    zip_path = os.path.join(project_dir, "analysis_bundle.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in zip_names:
            fp = os.path.join(bundle_path, name)
            if os.path.exists(fp):
                zf.write(fp, arcname=name)

    return {
        "bundle_path": bundle_path,
        "bundle_zip_path": zip_path,
        "ready": True,
        "files": zip_names,
        "generated_at": datetime.now(CHINA_TZ).isoformat(),
    }


def _build_readme(
    project_id: str,
    results: Dict[str, Any],
    coverage: Optional[Dict[str, Any]],
    cleaning: Optional[Dict[str, Any]],
    figure_manifest_count: int = 0,
) -> str:
    merged = results.get("merged") or {}
    data_spec = results.get("data_spec") or {}
    lines = [
        f"# Analysis-Ready Bundle — Project {project_id}",
        "",
        f"生成时间: {datetime.now(CHINA_TZ).isoformat()}",
        "",
        "## 文件说明",
        "- `merged.csv`: 合并（及可选清洗后）的多源表格，含 `_provenance_*` 与 `_cleaning_action`",
        "- `data_spec.json`: 本次任务数据需求（DataSpec）",
        "- `schema.json`: 列类型、字段映射与 merge 策略",
        "- `assets_index.json`: 全部数据资产索引",
        "- `provenance.jsonl`: 行级/表级来源记录",
        "- `quality_report.json`: 清洗前后与 merge 元信息",
    ]
    if figure_manifest_count:
        lines.append(
            "- `figure_manifest.jsonl`: 论文图表的识别、提取与校验说明（含 tier/confidence/limitations）"
        )
    lines.extend([
        "- `coverage_report.json`: 数据发现完备性（若已生成）",
        "",
        "## 数据需求 (DataSpec)",
        f"- 场景: {data_spec.get('scenario', 'general')}",
        f"- 实体字段: {', '.join(data_spec.get('entities_of_interest') or []) or '—'}",
        f"- 目标变量: {', '.join(data_spec.get('target_variables') or []) or '—'}",
        "",
        "## 合并摘要",
        f"- 行数: {merged.get('row_count', '—')}",
        f"- merge_id: {merged.get('merge_id', '—')}",
        f"- 清洗: {'是' if merged.get('cleaned_csv_path') else '否'}",
        "",
    ])
    if coverage:
        spec_cov = coverage.get("data_spec_coverage") or {}
        lines.extend([
            "## 完备性",
            f"- 得分: {coverage.get('completeness_score', '—')}/100",
            f"- DataSpec 字段覆盖: {spec_cov.get('data_spec_score', '—')}/100",
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
    if figure_manifest_count:
        lines.extend([
            "## 图表数据处理",
            f"- 共 {figure_manifest_count} 个图表 manifest；低置信提取默认需人工复核后才并入 merged.csv",
            "- 识别: caption 正则 + PDF 页定位/图块裁剪",
            "- 提取: L2 规则序列 或 L3 Qwen VLM（有 image_path 时）",
            "- 校验: FigureReview 确认 / 拒绝，见各条 manifest.validation",
            "",
        ])
    lines.append("## 方法")
    lines.append(
        "多源表格来自 PDF 抽取、外部数据集导入与（可选）人工确认图表；"
        "字段对齐由 DataSpec + 场景预设驱动；合并为纵向 stack（默认同实体 join 见 schema）。"
    )
    return "\n".join(lines)
