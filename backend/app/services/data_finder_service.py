"""多源科学数据查找与整合服务"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.project_modes import normalize_project_mode
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
        return path

    def _results_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "results.json")

    def load_results(self, project_id: str) -> Optional[Dict[str, Any]]:
        path = self._results_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

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
        req_res = await req_skill.run(
            {
                "research_question": research_question,
                "selected_hypothesis": selected_hypothesis,
                "project_mode": project_mode,
            },
            ctx,
        )
        data_requirements = req_res.data

        documents = self._load_project_documents(project_id)
        link_skill = PaperDataLinkExtractorSkill()
        link_res = await link_skill.run({"documents": documents}, ctx)
        paper_extractions = link_res.data.get("paper_extractions", [])

        ext_skill = ExternalDatasetSearchSkill()
        ext_res = await ext_skill.run(
            {
                "research_question": research_question,
                "dataset_keywords": data_requirements.get("dataset_keywords", []),
            },
            ctx,
        )

        figures_all: List[Dict[str, Any]] = []
        fig_skill = FigureDataExtractionSkill()
        from app.skills.data_finder.figure_vlm_series_skill import FigureVlmSeriesSkill

        series_skill = FigureVlmSeriesSkill()
        for pe in paper_extractions:
            doc = next((d for d in documents if d["id"] == pe.get("paper_id")), {})
            fig_res = await fig_skill.run(
                {
                    "figures_detected": pe.get("figures_detected", []),
                    "paper_id": pe.get("paper_id", ""),
                    "source_title": pe.get("source_title", ""),
                    "raw_text": doc.get("raw_text", ""),
                },
                ctx,
            )
            for fig in fig_res.data.get("figures", []):
                fig["extraction_method"] = "rule"
                fig["extraction_tier"] = "L1_metadata"
                series_res = await series_skill.run(
                    {
                        "caption": fig.get("caption", ""),
                        "possible_data_series": fig.get("possible_data_series", []),
                        "research_question": research_question,
                    },
                    ctx,
                )
                sdata = series_res.data or {}
                fig["extracted_series_preview"] = sdata.get("rows", [])
                fig["extraction_method"] = sdata.get("extraction_method", "rule_series")
                fig["extraction_tier"] = "L2_vlm" if sdata.get("extraction_method") == "vlm" else "L2_rule_series"
                fig["extraction_confidence"] = sdata.get("extraction_confidence", fig.get("extraction_confidence"))
                fig["needs_manual_review"] = sdata.get("needs_manual_review", True)
                fig["included_in_csv"] = False
                fig["review_status"] = "pending"
            figures_all.extend(fig_res.data.get("figures", []))

        payload = {
            "project_id": project_id,
            "project_mode": project_mode,
            "data_requirements": data_requirements,
            "paper_extractions": paper_extractions,
            "external_candidates": ext_res.data.get("candidates", []),
            "figures": figures_all,
            "extracted_tables": [],
            "alignments": [],
            "provenance": [],
            "merged": None,
            "warnings": link_res.warnings + ext_res.warnings,
        }
        self.save_results(project_id, payload)
        return payload

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

        self.save_results(project_id, results)
        return results

    async def run_align_schema(self, project_id: str, table_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        results = self.load_results(project_id) or {}
        project_mode = results.get("project_mode", "general")
        tables = results.get("extracted_tables", [])
        if table_ids:
            tables = [t for t in tables if t.get("table_id") in table_ids]

        align_skill = DatasetSchemaAlignmentSkill()
        alignments = []
        for tbl in tables:
            res = await align_skill.run(
                {"columns": tbl.get("columns", []), "project_mode": project_mode},
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
        merge_skill = DatasetMergeSkill()
        merge_res = await merge_skill.run(
            {
                "tables": results.get("extracted_tables", []),
                "alignments": results.get("alignments", []),
                "provenance": results.get("provenance", []),
                "output_dir": merged_dir,
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
        coverage = build_coverage_report(
            results,
            documents_count=doc_count,
            cleaning_report=cleaning_report,
        )
        results["coverage_report"] = coverage

        bundle_meta = build_analysis_bundle(
            project_id,
            self._project_dir(project_id),
            results,
            coverage_report=coverage,
            cleaning_report=cleaning_report,
        )
        results["analysis_bundle"] = bundle_meta

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

    async def run_gap_enrichment(
        self,
        project_id: str,
        refinement_queries: Optional[List[str]] = None,
        *,
        auto_import: bool = True,
    ) -> Dict[str, Any]:
        """Batch4: 基于 Coverage gaps 补搜并可选自动入库 HF 数据集。"""
        from app.services.data_finder_gap_search import (
            DEFAULT_COVERAGE_THRESHOLD,
            build_gap_search_queries,
            pick_import_candidates,
            should_run_gap_enrichment,
        )
        from app.services.external_dataset_import_service import auto_import_external_candidates
        from app.skills.data_finder._utils import new_id

        results = self.load_results(project_id) or {}
        threshold = float(
            (results.get("coverage_report") or {}).get("threshold")
            or DEFAULT_COVERAGE_THRESHOLD
        )
        coverage = results.get("coverage_report") or {}
        if not should_run_gap_enrichment(coverage, threshold=threshold):
            return {"skipped": True, "reason": "coverage 已达标"}

        gap_queries = build_gap_search_queries(
            coverage,
            refinement_queries,
            results.get("data_requirements"),
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
        existing = results.get("external_candidates") or []
        seen = {(c.get("dataset_name") or c.get("url") or "").lower() for c in existing}
        for c in new_candidates:
            key = (c.get("dataset_name") or c.get("url") or "").lower()
            if key and key not in seen:
                seen.add(key)
                existing.append(c)
        results["external_candidates"] = existing

        import_meta: Dict[str, Any] = {"imported_count": 0, "imported": [], "errors": []}
        imported_tables: List[Dict[str, Any]] = list(results.get("extracted_tables") or [])

        if auto_import:
            ext_dir = os.path.join(self._project_dir(project_id), "external")
            picks = pick_import_candidates(existing, max_count=2)
            import_meta = auto_import_external_candidates(picks, ext_dir, max_imports=2)
            for item in import_meta.get("imported") or []:
                table_id = new_id("ext")
                imported_tables.append({
                    "table_id": table_id,
                    "paper_id": "",
                    "source_title": item.get("dataset_name", "HF Dataset"),
                    "page": 0,
                    "caption": f"External import: {item.get('dataset_name')}",
                    "csv_path": item.get("csv_path"),
                    "columns": item.get("columns") or [],
                    "quality_score": 0.65,
                    "extraction_method": item.get("import_method", "hf_auto_import"),
                    "source_type": "hf_dataset",
                })
                results.setdefault("provenance", []).append({
                    "record_id": table_id,
                    "source_type": "hf_dataset",
                    "source_title": item.get("dataset_name", ""),
                    "paper_id": "",
                    "page": None,
                    "table_or_figure": table_id,
                    "extraction_method": item.get("import_method", "hf_auto_import"),
                    "confidence": 0.65,
                })

        results["extracted_tables"] = imported_tables
        results["external_import"] = import_meta

        if imported_tables:
            await self.run_align_schema(project_id)
            await self.run_merge(project_id)
            results = self.load_results(project_id) or results

        from app.services.data_finder_coverage import build_coverage_report

        coverage = build_coverage_report(
            results,
            documents_count=len(self._load_project_documents(project_id)),
            cleaning_report=(results.get("merged") or {}).get("cleaning_report"),
        )
        coverage["external_import_succeeded"] = import_meta.get("imported_count", 0)
        coverage["gap_queries"] = gap_queries
        results["coverage_report"] = coverage
        results["gap_enrichment"] = {
            "queries": gap_queries,
            "import_meta": import_meta,
            "skipped": False,
        }
        self.save_results(project_id, results)
        return results.get("gap_enrichment") or {}

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
