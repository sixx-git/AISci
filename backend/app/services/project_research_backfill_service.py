"""Pipeline 阶段完成后，将 Agent 产出回填到项目研究问题字段（仅填空，不覆盖用户已填内容）。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.project import Project

logger = logging.getLogger(__name__)

_BACKFILL_STAGES = frozenset({
    "problem_understanding",
    "knowledge_gap",
    "data_acquisition",
})


def _is_blank(text: Optional[str]) -> bool:
    return not text or not str(text).strip()


def _join_list(items: Any, *, bullet: bool = False) -> str:
    if isinstance(items, list):
        parts = [str(x).strip() for x in items if str(x).strip()]
        if not parts:
            return ""
        if bullet:
            return "\n".join(f"- {p}" for p in parts)
        return "\n".join(parts)
    if isinstance(items, str):
        return items.strip()
    return ""


def _pick_nonempty(*candidates: Any) -> str:
    for c in candidates:
        if c is None:
            continue
        s = str(c).strip()
        if s:
            return s
    return ""


def backfill_from_problem_understanding(project: Project, pu: Dict[str, Any]) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    if not isinstance(pu, dict):
        return updates

    if _is_blank(project.research_domain):
        domain = _pick_nonempty(pu.get("research_domain"))
        if domain:
            updates["research_domain"] = domain

    if _is_blank(project.research_goal):
        goal = _pick_nonempty(pu.get("scope_boundary"), pu.get("problem_statement"))
        if goal:
            updates["research_goal"] = goal

    if _is_blank(project.constraints):
        constraints = _join_list(pu.get("constraints"), bullet=True)
        if constraints:
            updates["constraints"] = constraints

    if _is_blank(project.expected_output):
        expected = _join_list(pu.get("expected_output"), bullet=True)
        if expected:
            updates["expected_output"] = expected

    rq = (project.research_question or "").strip()
    ps = _pick_nonempty(pu.get("problem_statement"))
    if ps and (_is_blank(rq) or len(rq) < 30):
        updates["research_question"] = ps

    return updates


def backfill_from_knowledge_gap(project: Project, kg: Dict[str, Any]) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    if not isinstance(kg, dict) or not _is_blank(project.research_background):
        return updates

    lines: List[str] = []
    for gap in (kg.get("knowledge_gaps") or [])[:5]:
        if isinstance(gap, dict):
            desc = _pick_nonempty(gap.get("description"))
            if desc:
                lines.append(f"- {desc}")
    if lines:
        updates["research_background"] = "\n".join(lines)
    return updates


def _extract_data_spec_block(da: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(da, dict):
        return {}
    for block in (
        da.get("search_summary"),
        da.get("extract"),
        da.get("search"),
        da.get("data_acquisition"),
        da,
    ):
        if not isinstance(block, dict):
            continue
        spec = block.get("data_spec")
        if isinstance(spec, dict):
            return spec
    return {}


def _collect_data_sources(da: Dict[str, Any]) -> List[str]:
    sources: List[str] = []
    if not isinstance(da, dict):
        return sources

    summary = da.get("search_summary") if isinstance(da.get("search_summary"), dict) else da
    merged = summary.get("merged") if isinstance(summary, dict) else {}
    if isinstance(merged, dict):
        path = _pick_nonempty(merged.get("csv_path"), merged.get("merged_csv_path"))
        if path:
            sources.append(f"合并数据集: {path}")

    for cand in (summary.get("external_candidates") or [])[:8]:
        if not isinstance(cand, dict):
            continue
        name = _pick_nonempty(cand.get("dataset_name"), cand.get("title"), cand.get("name"))
        platform = _pick_nonempty(cand.get("source_platform"))
        if name and platform:
            sources.append(f"{name} ({platform})")
        elif name:
            sources.append(name)

    for table in (summary.get("extracted_tables") or [])[:5]:
        if isinstance(table, dict):
            title = _pick_nonempty(table.get("source_title"), table.get("caption"))
            if title:
                sources.append(f"文献表格: {title}")

    return list(dict.fromkeys(sources))


def backfill_from_data_acquisition(
    project: Project,
    da: Dict[str, Any],
) -> tuple[Dict[str, str], Dict[str, Any]]:
    field_updates: Dict[str, str] = {}
    config_patch: Dict[str, Any] = {}
    if not isinstance(da, dict):
        return field_updates, config_patch

    if _is_blank(project.data_source):
        sources = _collect_data_sources(da)
        if sources:
            field_updates["data_source"] = "\n".join(sources)

    spec = _extract_data_spec_block(da)
    if not spec:
        return field_updates, config_patch

    hints: Dict[str, Any] = {}
    entities = [str(x).strip() for x in (spec.get("entities_of_interest") or []) if str(x).strip()]
    targets = [str(x).strip() for x in (spec.get("target_variables") or []) if str(x).strip()]
    if entities:
        hints["entities_of_interest"] = entities[:8]
    if targets:
        hints["target_variables"] = targets[:10]

    preferred: List[str] = []
    summary = da.get("search_summary") if isinstance(da.get("search_summary"), dict) else da
    for cand in (summary.get("external_candidates") or [])[:8]:
        if isinstance(cand, dict):
            platform = _pick_nonempty(cand.get("source_platform"))
            if platform:
                preferred.append(platform)
    if preferred:
        hints["preferred_sources"] = list(dict.fromkeys(preferred))[:8]

    merge_strategy = _pick_nonempty(
        (summary.get("merged") or {}).get("merge_strategy") if isinstance(summary.get("merged"), dict) else "",
    )
    if merge_strategy:
        hints["merge_strategy_hint"] = merge_strategy

    keywords = [str(x).strip() for x in (spec.get("dataset_keywords") or []) if str(x).strip()]
    if keywords and _is_blank((project.config or {}).get("data_spec_hints", {}).get("data_need_note")):
        hints["data_need_note"] = "推断数据关键词: " + ", ".join(keywords[:8])

    if hints:
        config_patch["data_spec_hints"] = hints

    return field_updates, config_patch


def _merge_config_hints(existing: Optional[Dict[str, Any]], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing or {})
    for key, value in patch.items():
        if key in ("entities_of_interest", "target_variables", "preferred_sources"):
            if merged.get(key):
                continue
            if value:
                merged[key] = value
        elif not merged.get(key) and value:
            merged[key] = value
    return merged


def backfill_project_research_fields(
    db: Session,
    project_id: str,
    results: Dict[str, Any],
    stage_key: str,
) -> Dict[str, Any]:
    """在指定 Pipeline 阶段完成后，将 Agent 产出写入项目空字段。"""
    if stage_key not in _BACKFILL_STAGES:
        return {}

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {}

    field_updates: Dict[str, str] = {}
    config_patch: Dict[str, Any] = {}

    if stage_key == "problem_understanding":
        field_updates.update(backfill_from_problem_understanding(
            project, results.get("problem_understanding") or {},
        ))
    elif stage_key == "knowledge_gap":
        field_updates.update(backfill_from_knowledge_gap(
            project, results.get("knowledge_gap") or {},
        ))
    elif stage_key == "data_acquisition":
        da_updates, cfg = backfill_from_data_acquisition(
            project, results.get("data_acquisition") or {},
        )
        field_updates.update(da_updates)
        config_patch.update(cfg)

    if not field_updates and not config_patch:
        return {}

    applied: Dict[str, Any] = {"fields": {}, "config": {}}

    for field, value in field_updates.items():
        if not hasattr(project, field):
            continue
        if _is_blank(getattr(project, field, None)) and not _is_blank(value):
            setattr(project, field, value)
            applied["fields"][field] = value

    if config_patch.get("data_spec_hints"):
        config = dict(project.config or {})
        existing_hints = config.get("data_spec_hints") if isinstance(config.get("data_spec_hints"), dict) else {}
        merged_hints = _merge_config_hints(existing_hints, config_patch["data_spec_hints"])
        if merged_hints != existing_hints:
            config["data_spec_hints"] = merged_hints
            project.config = config
            applied["config"]["data_spec_hints"] = merged_hints

    if applied["fields"] or applied["config"]:
        project.updated_at = datetime.now()
        db.commit()
        logger.info(
            "[ResearchBackfill] project=%s stage=%s fields=%s config_keys=%s",
            project_id,
            stage_key,
            list(applied["fields"].keys()),
            list(applied["config"].keys()),
        )

    return applied
