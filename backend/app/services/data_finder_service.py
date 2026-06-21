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
        results["merged"] = merge_res.data
        results.setdefault("warnings", []).extend(merge_res.warnings)
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
            csv_path = results["merged"].get("merged_csv_path")
        elif not csv_path and results.get("merged", {}).get("merged_csv_path"):
            csv_path = results["merged"]["merged_csv_path"]
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
        extra = {
            "data_finder_import": True,
            "provenance": provenance[:20],
            "source": "data_finder",
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


def get_data_finder_service(db: Session) -> DataFinderService:
    return DataFinderService(db)
