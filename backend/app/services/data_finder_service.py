"""多源科学数据查找与整合服务"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.data_scenario_presets import project_mode_to_scenario
from app.core.project_modes import normalize_project_mode
from app.schemas.data_integration import build_assets_index, build_figure_extraction_manifest, empty_data_spec, apply_data_spec_hints
from app.models.project import Document
from app.skills.data_finder.data_provenance_skill import DataProvenanceSkill
from app.skills.data_finder.data_requirement_understanding_skill import DataRequirementUnderstandingSkill
from app.skills.data_finder.dataset_merge_skill import DatasetMergeSkill
from app.skills.data_finder.dataset_schema_alignment_skill import DatasetSchemaAlignmentSkill
from app.skills.data_finder.external_dataset_search_skill import ExternalDatasetSearchSkill
from app.skills.data_finder.figure_data_extraction_skill import FigureDataExtractionSkill
from app.skills.data_finder.paper_data_link_extractor_skill import PaperDataLinkExtractorSkill
from app.skills.data_finder.pdf_table_extraction_skill import PdfTableExtractionSkill

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class DataFinderService:
    def __init__(self, db: Session):
        self.db = db
        self.storage_root = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "data_finder",
        )

    def _project_dir(self, project_id: str) -> str:
        path = os.path.join(self.storage_root, project_id)
        os.makedirs(path, exist_ok=True)
        os.makedirs(os.path.join(path, "tables"), exist_ok=True)
        os.makedirs(os.path.join(path, "merged"), exist_ok=True)
        os.makedirs(os.path.join(path, "bundle"), exist_ok=True)
        os.makedirs(os.path.join(path, "figures"), exist_ok=True)
        return path

    def _results_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "results.json")

    def load_results(self, project_id: str) -> Optional[Dict[str, Any]]:
        path = self._results_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("external_candidates"):
            from app.services.external_candidate_service import ensure_candidate_ids

            data["external_candidates"] = ensure_candidate_ids(data["external_candidates"])
        return data

    def save_results(self, project_id: str, payload: Dict[str, Any]) -> str:
        path = self._results_path(project_id)
        payload["updated_at"] = datetime.now(CHINA_TZ).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        return path

    def _load_project_documents(self, project_id: str) -> List[Dict[str, Any]]:
        docs = self.db.query(Document).filter(Document.project_id == project_id).all()
        out = []
        for d in docs:
            out.append({
                "id": d.id,
                "document_id": d.id,
                "title": d.title or d.filename,
                "filename": d.filename,
                "file_path": d.file_path,
                "file_type": d.file_type,
                "raw_text": d.raw_text or "",
                "abstract": d.abstract or "",
            })
        return out

    def _load_project_data_spec_hints(self, project_id: str) -> Dict[str, Any]:
        from app.services.project_service import ProjectService

        project = ProjectService(self.db).get_project(project_id)
        if not project:
            return {}
        config = project.config if isinstance(project.config, dict) else {}
        hints = config.get("data_spec_hints")
        return hints if isinstance(hints, dict) else {}

    def _load_project_config(self, project_id: str) -> Dict[str, Any]:
        from app.services.project_service import ProjectService

        project = ProjectService(self.db).get_project(project_id)
        if not project or not isinstance(project.config, dict):
            return {}
        return dict(project.config)

    def _resolve_gap_thresholds(
        self,
        project_id: str,
        run_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.services.data_finder_gap_search import resolve_gap_thresholds

        return resolve_gap_thresholds(self._load_project_config(project_id), run_options)

    def _project_research_domain(self, project_id: str) -> str:
        from app.services.project_service import ProjectService

        project = ProjectService(self.db).get_project(project_id)
        if not project:
            return ""
        return (project.research_domain or "").strip()

    def _build_external_search_context(
        self,
        *,
        project_id: str,
        research_question: str,
        data_requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.core.research_field import build_research_context

        req = data_requirements if isinstance(data_requirements, dict) else {}
        data_spec = req.get("data_spec") if isinstance(req.get("data_spec"), dict) else {}
        keywords = list(req.get("dataset_keywords") or [])
        keywords.extend(req.get("domain_keywords") or [])
        return build_research_context(
            research_question=research_question,
            research_domain=self._project_research_domain(project_id),
            keywords=keywords,
            data_spec=data_spec,
        )

    def _finalize_external_candidates(
        self,
        candidates: List[Dict[str, Any]],
        *,
        project_id: str,
        research_question: str,
        data_requirements: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        from app.core.research_field import filter_relevant_external_candidates
        from app.services.data_sources.base import normalize_legacy_candidate
        from app.services.external_candidate_service import ensure_candidate_ids

        normalized = [normalize_legacy_candidate(c) for c in (candidates or [])]
        ctx = self._build_external_search_context(
            project_id=project_id,
            research_question=research_question,
            data_requirements=data_requirements,
        )
        filtered = filter_relevant_external_candidates(normalized, ctx)
        return ensure_candidate_ids(filtered)

    async def run_search(
        self,
        project_id: str,
        research_question: str,
        selected_hypothesis: str = "",
        project_mode: str = "general",
    ) -> Dict[str, Any]:
        project_mode = normalize_project_mode(project_mode)
        ctx = {"stage": "data_finder", "project_id": project_id}

        req_skill = DataRequirementUnderstandingSkill()
        user_hints = self._load_project_data_spec_hints(project_id)
        req_res = await req_skill.run(
            {
                "research_question": research_question,
                "selected_hypothesis": selected_hypothesis,
                "project_mode": project_mode,
                "user_data_spec_hints": user_hints,
            },
            ctx,
        )
        data_requirements = req_res.data
        data_spec = data_requirements.get("data_spec") or empty_data_spec(
            research_question, project_mode_to_scenario(project_mode),
        )
        data_spec = apply_data_spec_hints(data_spec, user_hints)
        from app.core.domain_data_catalog import enrich_data_spec_from_domain

        research_domain = self._project_research_domain(project_id)
        data_spec = enrich_data_spec_from_domain(
            data_spec,
            research_domain=research_domain,
            file_description=str(data_spec.get("user_data_notes") or ""),
            research_question=research_question,
        )
        data_requirements["data_spec"] = data_spec

        project_config = self._load_project_config(project_id)
        documents = self._load_project_documents(project_id)
        literature_discovery: Optional[Dict[str, Any]] = None
        from app.services.literature_discovery_adapter import (
            discover_and_import_literature,
            should_auto_discover_literature,
        )

        if should_auto_discover_literature(len(documents), project_config):
            acq_cfg = (project_config.get("data_acquisition") or {})
            try:
                max_papers = int(acq_cfg.get("auto_literature_max_papers", 5))
            except (TypeError, ValueError):
                max_papers = 5
            literature_discovery = discover_and_import_literature(
                self.db,
                project_id,
                research_question,
                data_spec,
                max_papers=max_papers,
            )
            documents = self._load_project_documents(project_id)

        link_skill = PaperDataLinkExtractorSkill()
        link_res = await link_skill.run({"documents": documents}, ctx)
        paper_extractions = link_res.data.get("paper_extractions", [])

        from app.skills.data_finder.text_facts_extraction_skill import TextFactsExtractionSkill

        text_facts_skill = TextFactsExtractionSkill()
        text_facts_res = await text_facts_skill.run(
            {"documents": documents, "data_spec": data_spec},
            ctx,
        )
        text_facts = text_facts_res.data.get("text_facts") or []

        ext_skill = ExternalDatasetSearchSkill()
        research_domain = self._project_research_domain(project_id)
        ext_res = await ext_skill.run(
            {
                "research_question": research_question,
                "dataset_keywords": data_requirements.get("dataset_keywords", []),
                "research_domain": research_domain,
                "data_spec": data_spec,
            },
            ctx,
        )

        from app.services.data_sources.registry import search_all as registry_search
        from app.services.data_sources.base import normalize_legacy_candidate

        reg_res = await registry_search(research_question, data_spec, limit_per_source=4)
        ext_candidates = [
            normalize_legacy_candidate(c)
            for c in ext_res.data.get("candidates", [])
        ]
        seen_keys = {(c.get("dataset_name") or c.get("url") or "").lower() for c in ext_candidates}
        for c in reg_res.get("candidates", []):
            nc = normalize_legacy_candidate(c)
            key = (nc.get("dataset_name") or nc.get("url") or "").lower()
            if key and key not in seen_keys:
                seen_keys.add(key)
                ext_candidates.append(nc)

        ext_candidates = self._finalize_external_candidates(
            ext_candidates,
            project_id=project_id,
            research_question=research_question,
            data_requirements=data_requirements,
        )

        figures_all: List[Dict[str, Any]] = []
        fig_skill = FigureDataExtractionSkill()
        from app.skills.data_finder.figure_vlm_series_skill import FigureVlmSeriesSkill
        from app.skills.data_finder.pdf_figure_crop_skill import PdfFigureCropSkill

        series_skill = FigureVlmSeriesSkill()
        crop_skill = PdfFigureCropSkill()
        figures_dir = os.path.join(self._project_dir(project_id), "figures")

        for pe in paper_extractions:
            doc = next((d for d in documents if d["id"] == pe.get("paper_id")), {})
            file_path = doc.get("file_path", "")
            figures_detected = pe.get("figures_detected", [])

            cropped_figures = figures_detected
            if file_path and str(file_path).lower().endswith(".pdf") and figures_detected:
                crop_res = await crop_skill.run(
                    {
                        "file_path": file_path,
                        "paper_id": pe.get("paper_id", ""),
                        "figures": [
                            {
                                "figure_number": f.get("figure_number"),
                                "caption": f.get("caption", ""),
                            }
                            for f in figures_detected
                        ],
                        "output_dir": figures_dir,
                    },
                    ctx,
                )
                cropped_figures = crop_res.data.get("figures", figures_detected)

            fig_res = await fig_skill.run(
                {
                    "figures_detected": cropped_figures,
                    "paper_id": pe.get("paper_id", ""),
                    "source_title": pe.get("source_title", ""),
                    "raw_text": doc.get("raw_text", ""),
                },
                ctx,
            )
            for fig in fig_res.data.get("figures", []):
                # 合并裁剪结果中的 image_path / page
                crop_meta = next(
                    (c for c in cropped_figures if str(c.get("figure_number")) == str(fig.get("figure_number"))),
                    {},
                )
                if crop_meta.get("image_path"):
                    fig["image_path"] = crop_meta["image_path"]
                if crop_meta.get("page"):
                    fig["page"] = crop_meta["page"]
                if crop_meta.get("bbox"):
                    fig["bbox"] = crop_meta["bbox"]
                if crop_meta.get("crop_method"):
                    fig["crop_method"] = crop_meta["crop_method"]

                fig["extraction_method"] = "rule"
                fig["extraction_tier"] = "L1_metadata"
                series_res = await series_skill.run(
                    {
                        "caption": fig.get("caption", ""),
                        "possible_data_series": fig.get("possible_data_series", []),
                        "research_question": research_question,
                        "image_path": fig.get("image_path", ""),
                        "chart_type": fig.get("chart_type", "unknown"),
                        "axis_labels": fig.get("axis_labels", {}),
                    },
                    ctx,
                )
                sdata = series_res.data or {}
                fig["extracted_series_preview"] = sdata.get("rows", [])
                fig["extraction_method"] = sdata.get("extraction_method", "rule_series")
                fig["extraction_tier"] = sdata.get("extraction_tier", "L2_rule_series")
                fig["extraction_confidence"] = sdata.get("extraction_confidence", fig.get("extraction_confidence"))
                fig["digitization_checks"] = sdata.get("digitization_checks", [])
                fig["points_count"] = sdata.get("points_count", len(sdata.get("rows", [])))
                fig["schema_version"] = sdata.get("schema_version", "figure_series_v1")
                fig["needs_manual_review"] = sdata.get("needs_manual_review", True)
                fig["included_in_csv"] = False
                fig["review_status"] = "pending"
                fig["extraction_manifest"] = build_figure_extraction_manifest(fig)
            figures_all.extend(fig_res.data.get("figures", []))

        assets_index = build_assets_index({
            "extracted_tables": [],
            "figures": figures_all,
            "external_candidates": ext_candidates,
        })

        payload = {
            "project_id": project_id,
            "project_mode": project_mode,
            "data_spec": data_spec,
            "data_requirements": data_requirements,
            "literature_discovery": literature_discovery,
            "text_facts": text_facts,
            "paper_extractions": paper_extractions,
            "external_candidates": ext_candidates,
            "figures": figures_all,
            "assets_index": assets_index,
            "extracted_tables": [],
            "alignments": [],
            "provenance": [],
            "merged": None,
            "warnings": link_res.warnings + ext_res.warnings + reg_res.get("warnings", []) + text_facts_res.warnings,
        }
        self.save_results(project_id, payload)
        return payload

    async def run_search_quick(
        self,
        project_id: str,
        research_question: str,
        selected_hypothesis: str = "",
        project_mode: str = "general",
    ) -> Dict[str, Any]:
        """一键报告轻量发现：仅理解数据需求 + 外部数据集检索，跳过图表/VLM/文献再发现。"""
        project_mode = normalize_project_mode(project_mode)
        ctx = {"stage": "data_finder_quick", "project_id": project_id}
        user_hints = self._load_project_data_spec_hints(project_id)

        req_skill = DataRequirementUnderstandingSkill()
        req_res = await req_skill.run(
            {
                "research_question": research_question,
                "selected_hypothesis": selected_hypothesis,
                "project_mode": project_mode,
                "user_data_spec_hints": user_hints,
            },
            ctx,
        )
        data_requirements = req_res.data
        data_spec = data_requirements.get("data_spec") or empty_data_spec(
            research_question, project_mode_to_scenario(project_mode),
        )
        data_spec = apply_data_spec_hints(data_spec, user_hints)
        from app.core.domain_data_catalog import enrich_data_spec_from_domain

        research_domain = self._project_research_domain(project_id)
        data_spec = enrich_data_spec_from_domain(
            data_spec,
            research_domain=research_domain,
            file_description=str(data_spec.get("user_data_notes") or ""),
            research_question=research_question,
        )
        data_requirements["data_spec"] = data_spec

        ext_skill = ExternalDatasetSearchSkill()
        ext_res = await ext_skill.run(
            {
                "research_question": research_question,
                "dataset_keywords": data_requirements.get("dataset_keywords", []),
                "research_domain": research_domain,
                "data_spec": data_spec,
            },
            ctx,
        )

        from app.services.data_sources.registry import search_all as registry_search
        from app.services.data_sources.base import normalize_legacy_candidate

        reg_res = await registry_search(research_question, data_spec, limit_per_source=3)
        ext_candidates = [
            normalize_legacy_candidate(c) for c in ext_res.data.get("candidates", [])
        ]
        seen_keys = {(c.get("dataset_name") or c.get("url") or "").lower() for c in ext_candidates}
        for c in reg_res.get("candidates", []):
            nc = normalize_legacy_candidate(c)
            key = (nc.get("dataset_name") or nc.get("url") or "").lower()
            if key and key not in seen_keys:
                seen_keys.add(key)
                ext_candidates.append(nc)
        ext_candidates = self._finalize_external_candidates(
            ext_candidates,
            project_id=project_id,
            research_question=research_question,
            data_requirements=data_requirements,
        )

        assets_index = build_assets_index({
            "extracted_tables": [],
            "figures": [],
            "external_candidates": ext_candidates,
        })
        payload = {
            "project_id": project_id,
            "project_mode": project_mode,
            "data_spec": data_spec,
            "data_requirements": data_requirements,
            "literature_discovery": None,
            "text_facts": [],
            "paper_extractions": [],
            "external_candidates": ext_candidates,
            "figures": [],
            "assets_index": assets_index,
            "extracted_tables": [],
            "alignments": [],
            "provenance": [],
            "merged": None,
            "warnings": list(ext_res.warnings or []) + list(reg_res.get("warnings") or []),
            "quick_search": True,
        }
        self.save_results(project_id, payload)
        return payload

    async def run_fetch_supplementary(self, project_id: str) -> Dict[str, Any]:
        """下载并解析论文补充材料链接。"""
        results = self.load_results(project_id) or {}
        ctx = {"stage": "data_finder_fetch_si"}
        si_dir = os.path.join(self._project_dir(project_id), "supplementary")
        os.makedirs(si_dir, exist_ok=True)

        from app.skills.data_finder.supplementary_extraction_skill import SupplementaryExtractionSkill
        from app.skills.data_finder.supplementary_fetch_skill import SupplementaryFetchSkill

        fetch_skill = SupplementaryFetchSkill()
        extract_skill = SupplementaryExtractionSkill()
        all_si_tables: List[Dict[str, Any]] = []

        for pe in results.get("paper_extractions", []):
            links = pe.get("supplementary_links") or pe.get("data_links") or []
            if not links:
                continue
            paper_si_dir = os.path.join(si_dir, (pe.get("paper_id") or "unknown")[:12])
            fetch_res = await fetch_skill.run(
                {
                    "supplementary_links": links,
                    "paper_id": pe.get("paper_id", ""),
                    "output_dir": paper_si_dir,
                },
                ctx,
            )
            if not fetch_res.data.get("files"):
                continue
            ext_res = await extract_skill.run(
                {
                    "files": fetch_res.data["files"],
                    "output_dir": os.path.join(paper_si_dir, "tables"),
                    "source_title": pe.get("source_title", ""),
                },
                ctx,
            )
            all_si_tables.extend(ext_res.data.get("tables", []))

        if all_si_tables:
            existing = list(results.get("extracted_tables") or [])
            existing_ids = {t.get("table_id") for t in existing}
            for t in all_si_tables:
                if t.get("table_id") not in existing_ids:
                    existing.append(t)
            results["extracted_tables"] = existing
            for t in all_si_tables:
                results.setdefault("provenance", []).append({
                    "record_id": t["table_id"],
                    "source_type": "supplementary",
                    "source_title": t.get("source_title", ""),
                    "paper_id": t.get("paper_id", ""),
                    "page": None,
                    "table_or_figure": t.get("table_id"),
                    "extraction_method": t.get("extraction_method", "supplementary"),
                    "confidence": t.get("quality_score", 0.65),
                })
        else:
            results.setdefault("warnings", []).append("未从补充材料抽取到表格")

        results["supplementary_fetch"] = {"tables_added": len(all_si_tables)}
        results["assets_index"] = build_assets_index(results)
        self.save_results(project_id, results)
        return results

    async def run_data_acquisition(
        self,
        project_id: str,
        research_question: str,
        selected_hypothesis: str = "",
        project_mode: str = "general",
        *,
        auto_import: bool = True,
        gap_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """完整数据采集：discover → fetch → extract → align → merge → gap 闭环。"""
        steps: Dict[str, Any] = {}
        step_meta: Dict[str, Dict[str, Any]] = {}
        gap_opts = gap_options or {}
        quick_fast = bool(gap_opts.get("quick_report_fast"))

        discover_coro = (
            self.run_search_quick(project_id, research_question, selected_hypothesis, project_mode)
            if quick_fast
            else self.run_search(project_id, research_question, selected_hypothesis, project_mode)
        )
        await _timed_async_step(steps, step_meta, "discover", discover_coro)

        if quick_fast:
            steps["fetch_supplementary"] = {"skipped": True, "reason": "quick_report"}
            steps["extract"] = {"skipped": True, "reason": "quick_report"}
            step_meta["fetch_supplementary"] = {"duration_ms": 0, "error_code": None}
            step_meta["extract"] = {"duration_ms": 0, "error_code": None}
        else:
            await _timed_async_step(steps, step_meta, "fetch_supplementary", self.run_fetch_supplementary(project_id))
            await _timed_async_step(steps, step_meta, "extract", self.run_extract_tables(project_id))

        results = self.load_results(project_id) or {}

        if auto_import and results.get("external_candidates"):
            from app.services.external_dataset_import_service import auto_import_external_candidates_async
            from app.skills.data_finder._utils import new_id

            ext_dir = os.path.join(self._project_dir(project_id), "external")

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
                self.save_results(project_id, results)
                return import_meta

            await _timed_async_step(steps, step_meta, "fetch_external", _fetch_external())

        if results.get("extracted_tables"):
            await _timed_async_step(steps, step_meta, "align", self.run_align_schema(project_id))
            await _timed_async_step(steps, step_meta, "merge", self.run_merge(project_id))
        else:
            steps["align"] = {"skipped": True, "reason": "no_tables"}
            steps["merge"] = {"skipped": True, "reason": "no_tables"}
            step_meta["align"] = {"duration_ms": 0, "error_code": None}
            step_meta["merge"] = {"duration_ms": 0, "error_code": None}

        gap_loop: List[Dict[str, Any]] = []
        if gap_opts.get("enable_gap_search", True):
            async def _gap() -> List[Dict[str, Any]]:
                return await self.run_gap_loop(
                    project_id,
                    refinement_queries=gap_opts.get("refinement_queries"),
                    auto_import=auto_import if gap_opts.get("auto_import") is None else gap_opts.get("auto_import"),
                    run_options=gap_opts,
                )

            gap_loop = await _timed_async_step(steps, step_meta, "gap_loop", _gap()) or []

        final = self.load_results(project_id) or results
        from app.services.data_acquisition_release_gate import evaluate_release_gate

        release_gate = evaluate_release_gate(final)
        final["release_gate"] = release_gate
        final["data_acquisition"] = {
            "steps": list(steps.keys()),
            "stats": {
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
        self.save_results(project_id, final)
        return final

    def run_fetch_supplementary_sync(self, project_id: str) -> Dict[str, Any]:
        return asyncio.run(self.run_fetch_supplementary(project_id))

    def run_data_acquisition_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_data_acquisition(**kwargs))

    def run_gap_loop_sync(self, **kwargs) -> List[Dict[str, Any]]:
        return asyncio.run(self.run_gap_loop(**kwargs))

    async def run_extract_tables(self, project_id: str, paper_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        results = self.load_results(project_id) or {}
        documents = self._load_project_documents(project_id)
        if paper_ids:
            documents = [d for d in documents if d["id"] in paper_ids]

        ctx = {"stage": "data_finder_extract"}
        table_skill = PdfTableExtractionSkill()
        tables_dir = os.path.join(self._project_dir(project_id), "tables")
        all_tables: List[Dict[str, Any]] = []

        for doc in documents:
            if (doc.get("file_type") or "").lower() not in {".pdf", "pdf"} and not str(doc.get("file_path", "")).lower().endswith(".pdf"):
                continue
            pe = next(
                (p for p in results.get("paper_extractions", []) if p.get("paper_id") == doc["id"]),
                {},
            )
            res = await table_skill.run(
                {
                    "file_path": doc.get("file_path"),
                    "paper_id": doc["id"],
                    "source_title": doc.get("title") or doc.get("filename"),
                    "output_dir": tables_dir,
                    "tables_detected": pe.get("tables_detected", []),
                },
                ctx,
            )
            all_tables.extend(res.data.get("tables", []))

        results["extracted_tables"] = all_tables
        results.setdefault("warnings", [])
        if not all_tables:
            results["warnings"].append("未从 PDF 抽取到可导出表格（未编造）")

        provenance_records = [
            {
                "record_id": t["table_id"],
                "source_type": "paper_table",
                "source_title": t.get("source_title", ""),
                "paper_id": t.get("paper_id", ""),
                "page": t.get("page"),
                "table_or_figure": t.get("table_id"),
                "extraction_method": t.get("extraction_method", "pymupdf"),
                "confidence": t.get("quality_score", 0.0),
            }
            for t in all_tables
        ]
        prov_skill = DataProvenanceSkill()
        prov_res = await prov_skill.run({"records": provenance_records}, ctx)
        results["provenance"] = prov_res.data.get("provenance", [])
        results["assets_index"] = build_assets_index(results)

        self.save_results(project_id, results)
        return results

    async def run_align_schema(self, project_id: str, table_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        results = self.load_results(project_id) or {}
        project_mode = results.get("project_mode", "general")
        data_spec = results.get("data_spec") or (results.get("data_requirements") or {}).get("data_spec") or {}
        tables = results.get("extracted_tables", [])
        if table_ids:
            tables = [t for t in tables if t.get("table_id") in table_ids]

        align_skill = DatasetSchemaAlignmentSkill()
        alignments = []
        for tbl in tables:
            res = await align_skill.run(
                {
                    "columns": tbl.get("columns", []),
                    "project_mode": project_mode,
                    "data_spec": data_spec,
                },
                {"stage": "data_finder_align"},
            )
            item = dict(res.data)
            item["table_id"] = tbl.get("table_id")
            alignments.append(item)

        results["alignments"] = alignments
        self.save_results(project_id, results)
        return results

    async def run_merge(self, project_id: str) -> Dict[str, Any]:
        results = self.load_results(project_id) or {}
        merged_dir = os.path.join(self._project_dir(project_id), "merged")
        alignments = results.get("alignments", [])
        merge_strategy = "auto"
        if alignments:
            merge_strategy = alignments[0].get("merge_strategy", "auto")
        data_spec = results.get("data_spec") or {}
        if data_spec.get("merge_strategy_hint") in ("stack", "join"):
            merge_strategy = data_spec["merge_strategy_hint"]

        merge_skill = DatasetMergeSkill()
        merge_res = await merge_skill.run(
            {
                "tables": results.get("extracted_tables", []),
                "alignments": alignments,
                "provenance": results.get("provenance", []),
                "output_dir": merged_dir,
                "merge_strategy": merge_strategy,
            },
            {"stage": "data_finder_merge"},
        )
        merged_data = merge_res.data or {}
        results["merged"] = merged_data
        row_prov = merged_data.get("row_provenance") or []
        if row_prov:
            results["row_provenance"] = row_prov
        results.setdefault("warnings", []).extend(merge_res.warnings)

        from app.skills.data_finder.entity_resolution_skill import EntityResolutionSkill

        entity_skill = EntityResolutionSkill()
        entity_res = await entity_skill.run(
            {
                "tables": results.get("extracted_tables", []),
                "alignments": results.get("alignments", []),
                "data_spec": results.get("data_spec") or {},
                "project_mode": results.get("project_mode", "general"),
            },
            {"stage": "entity_resolution"},
        )
        results["entity_alignment"] = entity_res.data or {}
        if entity_res.warnings:
            results.setdefault("warnings", []).extend(entity_res.warnings)

        cleaning_report: Dict[str, Any] = {}
        merged_path = merged_data.get("merged_csv_path")
        if merged_path and os.path.exists(merged_path):
            from app.core.data_cleaning import clean_csv_file

            cleaned_path = os.path.join(merged_dir, f"{merged_data.get('merge_id', 'merged')}_cleaned.csv")
            try:
                cleaning_report = clean_csv_file(merged_path, cleaned_path)
                merged_data["cleaned_csv_path"] = cleaning_report.get("cleaned_csv_path")
                merged_data["cleaning_report"] = cleaning_report
                results["merged"] = merged_data
            except Exception as clean_err:
                logger.warning("Data Finder 清洗失败: %s", clean_err)
                results.setdefault("warnings", []).append(f"清洗未应用: {clean_err}")

        from app.services.data_finder_coverage import build_coverage_report
        from app.services.data_finder_bundle import build_analysis_bundle

        doc_count = len(self._load_project_documents(project_id))
        gap_thr = self._resolve_gap_thresholds(project_id)
        coverage = build_coverage_report(
            results,
            documents_count=doc_count,
            cleaning_report=cleaning_report,
            thresholds=gap_thr,
        )
        results["coverage_report"] = coverage

        results["assets_index"] = build_assets_index(results)
        bundle_meta = build_analysis_bundle(
            project_id,
            self._project_dir(project_id),
            results,
            coverage_report=coverage,
            cleaning_report=cleaning_report,
        )
        results["analysis_bundle"] = bundle_meta

        from app.services.data_acquisition_release_gate import evaluate_release_gate

        results["release_gate"] = evaluate_release_gate(results, config={"require_bundle_ready": bundle_meta.get("ready", False)})

        self.save_results(project_id, results)
        return results

    def import_to_dataset(
        self,
        project_id: str,
        csv_path: Optional[str] = None,
        merge_id: Optional[str] = None,
    ):
        from app.services.dataset_service import DatasetService

        results = self.load_results(project_id) or {}
        if merge_id and results.get("merged", {}).get("merge_id") == merge_id:
            merged = results["merged"]
            csv_path = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
        elif not csv_path and results.get("merged"):
            merged = results["merged"]
            csv_path = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
        elif not csv_path and results.get("extracted_tables"):
            csv_path = results["extracted_tables"][0].get("csv_path")

        if not csv_path or not os.path.exists(csv_path):
            raise FileNotFoundError("未找到可导入的 CSV，请先执行表格抽取或合并")

        ds_service = DatasetService(self.db)
        filename = os.path.basename(csv_path)
        dest_dir = ds_service._get_storage_dir(project_id)
        dest_path = os.path.join(dest_dir, f"datafinder_{filename}")
        shutil.copy2(csv_path, dest_path)

        provenance = results.get("provenance", [])
        bundle = results.get("analysis_bundle") or {}
        extra = {
            "data_finder_import": True,
            "provenance": provenance[:20],
            "source": "data_finder",
            "coverage_score": (results.get("coverage_report") or {}).get("completeness_score"),
            "bundle_path": bundle.get("bundle_path"),
        }
        ds = ds_service.create_dataset(
            project_id=project_id,
            filename=f"datafinder_{filename}",
            file_path=dest_path,
            file_size=os.path.getsize(dest_path),
            auto_analyze=True,
        )
        ds.source_type = "public"
        ds.extra_metadata = json.dumps(extra, ensure_ascii=False)
        self.db.commit()
        self.db.refresh(ds)
        return ds_service.to_response(ds)

    def run_search_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_search(**kwargs))

    def run_extract_tables_sync(self, project_id: str, paper_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        return asyncio.run(self.run_extract_tables(project_id, paper_ids))

    def run_align_schema_sync(self, project_id: str, table_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        return asyncio.run(self.run_align_schema(project_id, table_ids))

    def run_merge_sync(self, project_id: str) -> Dict[str, Any]:
        return asyncio.run(self.run_merge(project_id))

    def get_bundle_zip_path(self, project_id: str) -> str:
        results = self.load_results(project_id) or {}
        bundle = results.get("analysis_bundle") or {}
        zip_path = bundle.get("bundle_zip_path")
        if zip_path and os.path.exists(zip_path):
            return zip_path
        project_dir = self._project_dir(project_id)
        fallback = os.path.join(project_dir, "analysis_bundle.zip")
        if os.path.exists(fallback):
            return fallback
        raise FileNotFoundError("Analysis Bundle 尚未生成，请先执行合并")

    async def run_gap_loop(
        self,
        project_id: str,
        refinement_queries: Optional[List[str]] = None,
        *,
        auto_import: bool = True,
        run_options: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """多轮 gap 补搜直至达标或达到 max_gap_rounds。"""
        from app.services.data_finder_gap_search import should_run_gap_enrichment

        thr = self._resolve_gap_thresholds(project_id, run_options)
        max_rounds = int(thr.get("max_gap_rounds") or 2)
        history: List[Dict[str, Any]] = []

        for round_num in range(1, max_rounds + 1):
            results = self.load_results(project_id) or {}
            coverage = results.get("coverage_report") or {}
            if not should_run_gap_enrichment(
                coverage,
                threshold=thr["coverage_gap_threshold"],
                data_spec_threshold=thr["data_spec_gap_threshold"],
            ):
                history.append({"round": round_num, "skipped": True, "reason": "coverage 已达标"})
                break

            meta = await self.run_gap_enrichment(
                project_id,
                refinement_queries=refinement_queries,
                auto_import=auto_import,
                run_options=run_options,
                round_num=round_num,
            )
            history.append(meta)
            if meta.get("skipped"):
                break

        return history

    async def run_gap_enrichment(
        self,
        project_id: str,
        refinement_queries: Optional[List[str]] = None,
        *,
        auto_import: bool = True,
        run_options: Optional[Dict[str, Any]] = None,
        round_num: int = 1,
    ) -> Dict[str, Any]:
        """基于 Coverage / DataSpec gaps 补搜并可选自动入库外部数据集。"""
        from app.services.data_finder_gap_search import (
            build_gap_search_queries,
            pick_import_candidates,
            should_run_gap_enrichment,
        )
        from app.skills.data_finder._utils import new_id

        thr = self._resolve_gap_thresholds(project_id, run_options)
        results = self.load_results(project_id) or {}
        coverage = results.get("coverage_report") or {}
        score_before = coverage.get("completeness_score")
        spec_before = (coverage.get("data_spec_coverage") or {}).get("data_spec_score")

        if not should_run_gap_enrichment(
            coverage,
            threshold=thr["coverage_gap_threshold"],
            data_spec_threshold=thr["data_spec_gap_threshold"],
        ):
            return {"skipped": True, "reason": "coverage 已达标", "round": round_num}

        gap_queries = build_gap_search_queries(
            coverage,
            refinement_queries,
            results.get("data_requirements"),
            data_spec_coverage=coverage.get("data_spec_coverage"),
        )
        ctx = {"stage": "data_finder_gap"}
        ext_skill = ExternalDatasetSearchSkill()
        combined_query = " ".join(gap_queries[:4])[:400] or results.get("data_requirements", {}).get("data_need", "")
        ext_res = await ext_skill.run(
            {
                "research_question": combined_query,
                "dataset_keywords": gap_queries,
            },
            ctx,
        )
        new_candidates = ext_res.data.get("candidates", [])

        from app.services.data_sources.registry import search_all as registry_search

        data_spec = results.get("data_spec") or {}
        try:
            reg_res = await registry_search(combined_query, data_spec, limit_per_source=3)
            new_candidates.extend(reg_res.get("candidates") or [])
        except Exception as reg_err:
            logger.warning("Gap registry 检索失败: %s", reg_err)

        existing = results.get("external_candidates") or []
        seen = {(c.get("dataset_name") or c.get("url") or "").lower() for c in existing}
        added = 0
        for c in new_candidates:
            key = (c.get("dataset_name") or c.get("url") or "").lower()
            if key and key not in seen:
                seen.add(key)
                existing.append(c)
                added += 1
        results["external_candidates"] = existing

        import_meta: Dict[str, Any] = {"imported_count": 0, "imported": [], "errors": []}
        imported_tables: List[Dict[str, Any]] = list(results.get("extracted_tables") or [])

        if auto_import:
            from app.services.external_dataset_import_service import auto_import_external_candidates_async

            ext_dir = os.path.join(self._project_dir(project_id), "external")
            picks = pick_import_candidates(existing, max_count=2)
            import_meta = await auto_import_external_candidates_async(picks, ext_dir, max_imports=2)
            for item in import_meta.get("imported") or []:
                table_id = new_id("ext")
                imported_tables.append({
                    "table_id": table_id,
                    "paper_id": "",
                    "source_title": item.get("dataset_name", "External Dataset"),
                    "page": 0,
                    "caption": f"Gap import: {item.get('dataset_name')}",
                    "csv_path": item.get("csv_path"),
                    "columns": item.get("columns") or [],
                    "quality_score": 0.65,
                    "extraction_method": item.get("import_method", "gap_auto_import"),
                    "source_type": item.get("provenance_source_type", "external_csv"),
                })
                results.setdefault("provenance", []).append({
                    "record_id": table_id,
                    "source_type": "external_csv",
                    "source_title": item.get("dataset_name", ""),
                    "paper_id": "",
                    "page": None,
                    "table_or_figure": table_id,
                    "extraction_method": item.get("import_method", "gap_auto_import"),
                    "confidence": 0.65,
                })

        results["extracted_tables"] = imported_tables
        results["external_import"] = import_meta

        if imported_tables:
            await self.run_align_schema(project_id)
            await self.run_merge(project_id)
            results = self.load_results(project_id) or results
        else:
            from app.services.data_finder_coverage import build_coverage_report

            coverage = build_coverage_report(
                results,
                documents_count=len(self._load_project_documents(project_id)),
                cleaning_report=(results.get("merged") or {}).get("cleaning_report"),
                thresholds=thr,
            )
            coverage["external_import_succeeded"] = import_meta.get("imported_count", 0)
            coverage["gap_queries"] = gap_queries
            results["coverage_report"] = coverage
            self.save_results(project_id, results)

        results = self.load_results(project_id) or results
        coverage_after = results.get("coverage_report") or {}
        enrichment = {
            "round": round_num,
            "queries": gap_queries,
            "candidates_added": added,
            "import_meta": import_meta,
            "skipped": False,
            "score_before": score_before,
            "score_after": coverage_after.get("completeness_score"),
            "data_spec_score_before": spec_before,
            "data_spec_score_after": (coverage_after.get("data_spec_coverage") or {}).get("data_spec_score"),
            "thresholds": {
                "coverage": thr["coverage_gap_threshold"],
                "data_spec": thr["data_spec_gap_threshold"],
            },
        }
        results["gap_enrichment"] = enrichment
        self.save_results(project_id, results)
        return enrichment

    def run_gap_enrichment_sync(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self.run_gap_enrichment(**kwargs))

    def resolve_data_citation(self, project_id: str, citation_id: str) -> Optional[Dict[str, Any]]:
        from app.core.data_citation import resolve_data_citation

        results = self.load_results(project_id) or {}
        return resolve_data_citation(
            citation_id,
            provenance=results.get("provenance") or [],
            row_provenance=results.get("row_provenance") or [],
        )


def get_data_finder_service(db: Session) -> DataFinderService:
    return DataFinderService(db)


async def _timed_async_step(
    steps: Dict[str, Any],
    step_meta: Dict[str, Dict[str, Any]],
    key: str,
    coro,
) -> Any:
    """执行异步步骤并记录 duration_ms / error_code。"""
    t0 = time.perf_counter()
    error_code = None
    try:
        result = await coro
        steps[key] = result
        return result
    except Exception as exc:
        error_code = type(exc).__name__
        steps[key] = {"error": str(exc)[:200], "error_code": error_code}
        logger.warning("data_acquisition step %s failed: %s", key, exc)
        raise
    finally:
        step_meta[key] = {
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": error_code,
        }


def _summarize_step(step_data: Any) -> Dict[str, Any]:
    if isinstance(step_data, list):
        return {
            "rounds": len(step_data),
            "last_score_after": (step_data[-1] or {}).get("score_after") if step_data else None,
        }
    if not isinstance(step_data, dict):
        return {"ok": bool(step_data)}
    if step_data.get("skipped"):
        return {"skipped": True, "reason": step_data.get("reason")}
    if step_data.get("error_code"):
        return {"error": step_data.get("error"), "error_code": step_data.get("error_code")}
    if "score_after" in step_data:
        return {
            "round": step_data.get("round"),
            "score_before": step_data.get("score_before"),
            "score_after": step_data.get("score_after"),
            "imported": (step_data.get("import_meta") or {}).get("imported_count", 0),
        }
    if "imported_count" in step_data:
        return {"imported_count": step_data.get("imported_count"), "errors": step_data.get("errors", [])[:2]}
    if "tables_added" in step_data:
        return {"tables_added": step_data.get("tables_added")}
    if "extracted_tables" in step_data:
        return {"tables": len(step_data.get("extracted_tables") or [])}
    if "row_count" in step_data:
        return {"row_count": step_data.get("row_count"), "merge_strategy": step_data.get("merge_strategy")}
    return {"keys": list(step_data.keys())[:6]}
