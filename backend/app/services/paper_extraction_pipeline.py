"""论文抽表抽图 + 合并建库 — 独立工具链，不参与 Pipeline 自迭代。

供以下入口调用：
- POST /api/v1/data-finder/build-library
- backend/scripts/run_paper_extraction_pipeline.py
- DataFinderService.run_paper_extraction_pipeline()
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.services.data_acquisition_release_gate import evaluate_release_gate
from app.services.data_finder_service import (
    ACQUISITION_MODE_FULL,
    _summarize_step,
    _timed_async_step,
)

if TYPE_CHECKING:
    from app.services.data_finder_service import DataFinderService

logger = logging.getLogger(__name__)

PIPELINE_LABEL = "paper_extraction_library"


async def run_paper_extraction_pipeline(
    service: "DataFinderService",
    project_id: str,
    research_question: str,
    selected_hypothesis: str = "",
    project_mode: str = "general",
    *,
    auto_import: bool = True,
    enable_gap_search: bool = False,
    gap_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从已入库论文抽取表格/图表，对齐合并为分析库（含可选 Gap 补搜与 Release Gate）。"""
    steps: Dict[str, Any] = {}
    step_meta: Dict[str, Dict[str, Any]] = {}
    gap_opts = dict(gap_options or {})
    gap_opts.setdefault("acquisition_mode", ACQUISITION_MODE_FULL)

    await _timed_async_step(
        steps,
        step_meta,
        "discover",
        service.run_search(project_id, research_question, selected_hypothesis, project_mode),
    )
    await _timed_async_step(
        steps,
        step_meta,
        "fetch_supplementary",
        service.run_fetch_supplementary(project_id),
    )
    await _timed_async_step(
        steps,
        step_meta,
        "extract",
        service.run_extract_tables(project_id),
    )

    results = service.load_results(project_id) or {}

    if auto_import and results.get("external_candidates"):
        from app.services.external_dataset_import_service import auto_import_external_candidates_async
        from app.skills.data_finder._utils import new_id

        ext_dir = os.path.join(service._project_dir(project_id), "external")

        async def _fetch_external() -> Dict[str, Any]:
            import_meta = await auto_import_external_candidates_async(
                results.get("external_candidates", []),
                ext_dir,
                max_imports=2,
            )
            for item in import_meta.get("imported") or []:
                table_id = item.get("table_id") or new_id("ext")
                results.setdefault("extracted_tables", []).append({
                    "table_id": table_id,
                    "paper_id": "",
                    "source_title": item.get("dataset_name", "External"),
                    "page": 0,
                    "caption": f"External: {item.get('dataset_name')}",
                    "csv_path": item.get("csv_path"),
                    "columns": item.get("columns") or [],
                    "quality_score": 0.65,
                    "extraction_method": item.get("import_method", "external_import"),
                    "source_type": item.get("provenance_source_type", "external_csv"),
                })
            service.save_results(project_id, results)
            return import_meta

        await _timed_async_step(steps, step_meta, "fetch_external", _fetch_external())
    else:
        service._mark_steps_skipped(steps, step_meta, ("fetch_external",), reason="no_candidates_or_disabled")

    results = service.load_results(project_id) or {}
    if results.get("extracted_tables"):
        await _timed_async_step(steps, step_meta, "align", service.run_align_schema(project_id))
        await _timed_async_step(steps, step_meta, "merge", service.run_merge(project_id))
    else:
        service._mark_steps_skipped(steps, step_meta, ("align", "merge"), reason="no_tables")

    gap_loop: List[Dict[str, Any]] = []
    if enable_gap_search:
        async def _gap() -> List[Dict[str, Any]]:
            return await service.run_gap_loop(
                project_id,
                refinement_queries=gap_opts.get("refinement_queries"),
                auto_import=auto_import if gap_opts.get("auto_import") is None else gap_opts.get("auto_import"),
                run_options=gap_opts,
            )

        gap_loop = await _timed_async_step(steps, step_meta, "gap_loop", _gap()) or []
    else:
        service._mark_steps_skipped(steps, step_meta, ("gap_loop",), reason="disabled")

    final = service.load_results(project_id) or {}
    release_gate = evaluate_release_gate(final)
    final["release_gate"] = release_gate
    final["data_acquisition"] = {
        "mode": PIPELINE_LABEL,
        "legacy_mode": ACQUISITION_MODE_FULL,
        "steps": list(steps.keys()),
        "stats": {
            "acquisition_mode": PIPELINE_LABEL,
            "external_candidates": len(final.get("external_candidates") or []),
            "tables": len(final.get("extracted_tables") or []),
            "merged_rows": (final.get("merged") or {}).get("row_count"),
            "gap_rounds": len(gap_loop),
            "release_gate_passed": release_gate.get("passed"),
            "total_duration_ms": sum(m.get("duration_ms") or 0 for m in step_meta.values()),
        },
        "step_details": {
            k: {**_summarize_step(v), **step_meta.get(k, {})}
            for k, v in steps.items()
        },
    }
    service.save_results(project_id, final)
    logger.info(
        "[PaperExtractionPipeline] project=%s tables=%s merged_rows=%s gate=%s",
        project_id,
        final["data_acquisition"]["stats"]["tables"],
        final["data_acquisition"]["stats"]["merged_rows"],
        release_gate.get("passed"),
    )
    return final
