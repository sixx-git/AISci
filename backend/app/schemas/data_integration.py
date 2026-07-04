"""多源数据整合 — DataSpec / DataAsset / ExtractionManifest 契约"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


# 场景预设（与 project_mode 映射见 data_scenario_presets）
DATA_SCENARIOS = ("general", "ml_benchmark", "federated_learning")

DEFAULT_PREFERRED_SOURCES = [
    "uploaded_pdf", "bibtex", "openalex", "zenodo", "figshare",
    "huggingface", "kaggle", "supplementary",
]


def empty_data_spec(
    research_question: str = "",
    scenario: str = "general",
) -> Dict[str, Any]:
    return {
        "research_question": research_question[:500],
        "scenario": scenario if scenario in DATA_SCENARIOS else "general",
        "entities_of_interest": [],
        "target_variables": [],
        "column_synonyms": {},
        "dataset_keywords": [],
        "domain_keywords": [],
        "preferred_sources": list(DEFAULT_PREFERRED_SOURCES),
        "merge_strategy_hint": "auto",
        "output_format": "csv",
        "constraints": {
            "require_provenance": True,
            "min_confidence": 0.5,
        },
    }


def merge_data_requirements_legacy(data_spec: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧 data_requirements 字段（前端与 gap 搜索仍可读）。"""
    return {
        "data_need": data_spec.get("research_question") or data_spec.get("data_need", ""),
        "target_variables": data_spec.get("target_variables", []),
        "expected_metrics": data_spec.get("target_variables", []),
        "domain_keywords": data_spec.get("domain_keywords", []),
        "dataset_keywords": data_spec.get("dataset_keywords", []),
        "preferred_sources": data_spec.get("preferred_sources", []),
        "output_format": data_spec.get("output_format", "csv"),
        "scenario": data_spec.get("scenario", "general"),
        "entities_of_interest": data_spec.get("entities_of_interest", []),
        "merge_strategy_hint": data_spec.get("merge_strategy_hint", "auto"),
    }


def build_figure_extraction_manifest(fig: Dict[str, Any]) -> Dict[str, Any]:
    """为论文图表生成可读的识别/提取/校验说明。"""
    method = fig.get("extraction_method", "rule")
    tier = fig.get("extraction_tier", "L1_metadata")
    confidence = fig.get("extraction_confidence", 0.0)
    has_image = bool(fig.get("image_path"))

    limitations = []
    if method == "rule" or method == "rule_series":
        limitations.append("基于 caption 规则推断，未做像素级曲线数字化")
    if method == "vlm" and confidence < 0.65:
        limitations.append("VLM 提取置信度偏低，建议人工复核")
    if method == "vlm_digitize" and tier != "L4_digitize":
        limitations.append("VLM 数字化未达 L4 门槛（点数或校验不足）")
    if not has_image and method != "vlm":
        limitations.append("未裁剪 PDF 图块，未启用视觉模型")

    checks = ["caption_present"]
    if fig.get("axis_labels", {}).get("x") or fig.get("axis_labels", {}).get("y"):
        checks.append("axis_label_present")
    if fig.get("extracted_series_preview"):
        checks.append("series_preview_available")
    auto_checks = list(fig.get("digitization_checks") or [])
    for c in auto_checks:
        if c not in checks:
            checks.append(c)

    points_count = fig.get("points_count")
    if points_count is None and fig.get("extracted_series_preview"):
        points_count = len(fig.get("extracted_series_preview") or [])

    identification: Dict[str, Any] = {
        "method": "caption_regex + page_layout" if has_image else "caption_regex",
        "caption": fig.get("caption", ""),
        "page": fig.get("page"),
        "figure_number": fig.get("figure_number"),
        "chart_type": fig.get("chart_type", "unknown"),
        "image_path": fig.get("image_path"),
    }
    if fig.get("bbox"):
        identification["bbox"] = fig.get("bbox")
    if fig.get("crop_method"):
        identification["crop_method"] = fig.get("crop_method")

    extraction: Dict[str, Any] = {
        "tier": tier,
        "method": method,
        "confidence": confidence,
        "rows_preview": (fig.get("extracted_series_preview") or [])[:6],
        "limitations": limitations,
        "schema_version": fig.get("schema_version", "figure_series_v1"),
    }
    if points_count is not None:
        extraction["points_count"] = points_count

    human_required = fig.get("needs_manual_review", True)
    if tier == "L4_digitize" and confidence >= 0.75:
        limitations.append("L4 点列已校验，仍建议 spot-check 关键点")

    return {
        "figure_id": fig.get("figure_id", ""),
        "identification": identification,
        "extraction": extraction,
        "validation": {
            "status": fig.get("review_status", "pending"),
            "checks": checks,
            "auto_checks": auto_checks,
            "needs_manual_review": human_required,
            "human_review_required": human_required,
            "included_in_merged_csv": fig.get("included_in_csv", False),
        },
    }


def table_to_data_asset(table: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_id": table.get("table_id", ""),
        "source_type": table.get("source_type", "paper_table"),
        "source_ref": table.get("paper_id", ""),
        "source_title": table.get("source_title", ""),
        "extraction_tier": "L2_structured",
        "extraction_method": table.get("extraction_method", "pymupdf"),
        "confidence": table.get("quality_score", 0.0),
        "csv_path": table.get("csv_path"),
        "columns": table.get("columns", []),
        "row_count": table.get("row_count"),
    }


def figure_to_data_asset(fig: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_id": fig.get("figure_id", ""),
        "source_type": "figure_series",
        "source_ref": fig.get("paper_id", ""),
        "source_title": fig.get("source_title", ""),
        "extraction_tier": fig.get("extraction_tier", "L1_metadata"),
        "extraction_method": fig.get("extraction_method", "rule"),
        "confidence": fig.get("extraction_confidence", 0.0),
        "csv_path": fig.get("series_csv_path"),
        "extraction_manifest": fig.get("extraction_manifest") or build_figure_extraction_manifest(fig),
    }


def build_assets_index(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """汇总 results 中全部 DataAsset。"""
    assets: List[Dict[str, Any]] = []
    for tbl in results.get("extracted_tables") or []:
        assets.append(table_to_data_asset(tbl))
    for fig in results.get("figures") or []:
        assets.append(figure_to_data_asset(fig))
    for cand in results.get("external_candidates") or []:
        if cand.get("imported_csv_path"):
            assets.append({
                "asset_id": cand.get("dataset_name", "ext"),
                "source_type": "external_csv",
                "source_ref": cand.get("url", ""),
                "source_title": cand.get("dataset_name", ""),
                "extraction_tier": "L2_structured",
                "extraction_method": cand.get("import_method", "hf_auto_import"),
                "confidence": cand.get("confidence", 0.65),
                "csv_path": cand.get("imported_csv_path"),
            })
    return assets


def parse_comma_list(text: str) -> List[str]:
    """将逗号/分号/换行分隔的文本解析为去重列表。"""
    if not text or not str(text).strip():
        return []
    parts = re.split(r"[,;，；\n]+", str(text))
    out: List[str] = []
    seen: Set[str] = set()
    for p in parts:
        v = p.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v[:80])
    return out[:20]


def apply_data_spec_hints(
    data_spec: Dict[str, Any],
    hints: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """将用户在研究问题页填写的 DataSpec 提示合并进自动推断的 spec。"""
    if not hints or not isinstance(hints, dict):
        return data_spec

    spec = dict(data_spec)
    for key in ("entities_of_interest", "target_variables", "preferred_sources"):
        val = hints.get(key)
        if isinstance(val, list) and val:
            merged = list(dict.fromkeys([*(spec.get(key) or []), *[str(x) for x in val if x]]))
            spec[key] = merged[:20]
        elif isinstance(val, str) and val.strip():
            parsed = parse_comma_list(val)
            if parsed:
                merged = list(dict.fromkeys([*(spec.get(key) or []), *parsed]))
                spec[key] = merged[:20]

    hint = hints.get("merge_strategy_hint")
    if hint in ("auto", "stack", "join"):
        spec["merge_strategy_hint"] = hint

    user_note = hints.get("data_need_note") or hints.get("notes")
    if isinstance(user_note, str) and user_note.strip():
        spec["user_data_notes"] = user_note.strip()[:500]

    from app.core.domain_data_catalog import enrich_data_spec_from_domain

    domain_kw = hints.get("domain_keywords")
    if isinstance(domain_kw, list) and domain_kw:
        merged = list(dict.fromkeys([*(spec.get("domain_keywords") or []), *[str(x) for x in domain_kw if x]]))
        spec["domain_keywords"] = merged[:20]

    spec = enrich_data_spec_from_domain(
        spec,
        research_domain=str(hints.get("research_category") or hints.get("research_domain") or ""),
        file_description=str(user_note or ""),
        research_question=str(spec.get("research_question") or ""),
    )

    return spec
