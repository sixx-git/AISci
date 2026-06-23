"""外部数据候选 — 用户手动下载后上传并纳入 merge"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))

MANUAL_AVAILABILITY = frozenset({"catalog_only", "metadata_only", "url_only"})
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
STATUS_PENDING = "pending_download"
STATUS_PROCESSING = "processing"
STATUS_MERGED = "merged"
STATUS_FAILED = "failed"
STATUS_AUTO = "auto_imported"


def ensure_candidate_ids(candidates: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    from app.skills.data_finder._utils import new_id

    out: List[Dict[str, Any]] = []
    for raw in candidates or []:
        c = dict(raw)
        if not c.get("candidate_id"):
            c["candidate_id"] = new_id("cand")
        sync_candidate_upload_status(c)
        out.append(c)
    return out


def sync_candidate_upload_status(candidate: Dict[str, Any]) -> None:
    """根据 availability / imported 同步 user_upload_status。"""
    if candidate.get("user_upload_status") == STATUS_PROCESSING:
        return
    if candidate.get("imported") or candidate.get("imported_csv_path") or candidate.get("linked_table_id"):
        if candidate.get("user_upload_status") == STATUS_FAILED:
            return
        if candidate.get("user_upload_filename") or candidate.get("user_upload_status") == STATUS_MERGED:
            candidate["user_upload_status"] = STATUS_MERGED
        else:
            candidate["user_upload_status"] = STATUS_AUTO
        return
    if candidate.get("user_upload_status") == STATUS_FAILED:
        return
    availability = candidate.get("availability") or ""
    import_supported = candidate.get("import_supported", True)
    if availability in MANUAL_AVAILABILITY or import_supported is False:
        candidate["user_upload_status"] = STATUS_PENDING
    else:
        candidate.setdefault("user_upload_status", "pending_auto")


def list_manual_candidates(candidates: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """需用户手动下载的候选（含已上传处理中/已完成）。"""
    ensured = ensure_candidate_ids(candidates)
    manual: List[Dict[str, Any]] = []
    for c in ensured:
        availability = str(c.get("availability") or "")
        if availability in MANUAL_AVAILABILITY or c.get("import_supported") is False:
            manual.append(c)
        elif c.get("user_upload_status") in (STATUS_PENDING, STATUS_PROCESSING, STATUS_MERGED, STATUS_FAILED):
            if c.get("user_upload_filename") or c.get("linked_table_id"):
                manual.append(c)
    return manual


def _find_candidate(
    candidates: List[Dict[str, Any]],
    candidate_id: str,
) -> Tuple[int, Dict[str, Any]]:
    for i, c in enumerate(candidates):
        if c.get("candidate_id") == candidate_id:
            return i, c
    raise ValueError(f"未找到 candidate_id={candidate_id}")


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "upload.csv")
    return re.sub(r"[^\w.\-]", "_", base)[:120] or "upload.csv"


class ExternalCandidateService:
    def __init__(self, db: Session):
        self.db = db
        from app.services.data_finder_service import get_data_finder_service

        self._df = get_data_finder_service(db)

    async def upload_and_merge(
        self,
        project_id: str,
        candidate_id: str,
        *,
        source_path: str,
        original_filename: str,
    ) -> Dict[str, Any]:
        results = self._df.load_results(project_id) or {}
        candidates = ensure_candidate_ids(results.get("external_candidates"))
        idx, cand = _find_candidate(candidates, candidate_id)

        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的上传格式 {ext}，请使用 CSV/TSV/XLSX")

        cand["user_upload_status"] = STATUS_PROCESSING
        cand["user_upload_filename"] = original_filename
        cand["user_upload_error"] = None
        cand["user_upload_started_at"] = datetime.now(CHINA_TZ).isoformat()
        candidates[idx] = cand
        results["external_candidates"] = candidates
        self._df.save_results(project_id, results)

        upload_dir = os.path.join(self._df._project_dir(project_id), "user_uploads", candidate_id)
        os.makedirs(upload_dir, exist_ok=True)
        dest_path = os.path.join(upload_dir, _safe_filename(original_filename))
        shutil.copy2(source_path, dest_path)

        try:
            from app.skills.data_finder.tabular_file_extraction_skill import TabularFileExtractionSkill

            tables_dir = os.path.join(self._df._project_dir(project_id), "tables")
            os.makedirs(tables_dir, exist_ok=True)
            skill = TabularFileExtractionSkill()
            extract_res = await skill.run(
                {
                    "file_path": dest_path,
                    "source_title": cand.get("dataset_name") or original_filename,
                    "output_dir": tables_dir,
                },
                {"stage": "external_candidate_upload"},
            )
            tables = extract_res.data.get("tables") or []
            if not tables:
                err = (extract_res.errors or extract_res.warnings or ["未能解析表格"])[0]
                raise ValueError(str(err))

            tbl = dict(tables[0])
            tbl["candidate_id"] = candidate_id
            tbl["source_type"] = "user_upload_external"
            tbl["paper_id"] = ""
            tbl["extraction_method"] = "user_upload"
            tbl["quality_score"] = tbl.get("quality_score", 0.75)

            results = self._df.load_results(project_id) or {}
            candidates = ensure_candidate_ids(results.get("external_candidates"))
            _, cand = _find_candidate(candidates, candidate_id)

            existing = [
                t for t in (results.get("extracted_tables") or [])
                if t.get("candidate_id") != candidate_id
            ]
            existing.append(tbl)
            results["extracted_tables"] = existing

            prov = [p for p in (results.get("provenance") or []) if p.get("record_id") != tbl.get("table_id")]
            prov.append({
                "record_id": tbl["table_id"],
                "source_type": "user_upload_external",
                "source_title": cand.get("dataset_name") or original_filename,
                "paper_id": "",
                "page": None,
                "table_or_figure": candidate_id,
                "url": cand.get("url", ""),
                "extraction_method": "user_upload",
                "confidence": tbl.get("quality_score", 0.75),
            })
            results["provenance"] = prov

            cand["user_upload_status"] = STATUS_MERGED
            cand["imported"] = True
            cand["linked_table_id"] = tbl["table_id"]
            cand["imported_csv_path"] = tbl.get("csv_path")
            cand["user_upload_completed_at"] = datetime.now(CHINA_TZ).isoformat()
            for i, c in enumerate(candidates):
                if c.get("candidate_id") == candidate_id:
                    candidates[i] = cand
                    break
            results["external_candidates"] = candidates
            self._df.save_results(project_id, results)

            await self._df.run_align_schema(project_id)
            merged = await self._df.run_merge(project_id)
            return merged
        except Exception as exc:
            logger.warning("外部候选上传失败 %s: %s", candidate_id, exc)
            results = self._df.load_results(project_id) or {}
            candidates = ensure_candidate_ids(results.get("external_candidates"))
            try:
                _, cand = _find_candidate(candidates, candidate_id)
                cand["user_upload_status"] = STATUS_FAILED
                cand["user_upload_error"] = str(exc)[:300]
                cand["user_upload_completed_at"] = datetime.now(CHINA_TZ).isoformat()
                for i, c in enumerate(candidates):
                    if c.get("candidate_id") == candidate_id:
                        candidates[i] = cand
                        break
                results["external_candidates"] = candidates
                self._df.save_results(project_id, results)
            except ValueError:
                pass
            raise

    def upload_and_merge_sync(
        self,
        project_id: str,
        candidate_id: str,
        *,
        source_path: str,
        original_filename: str,
    ) -> Dict[str, Any]:
        return asyncio.run(self.upload_and_merge(
            project_id, candidate_id,
            source_path=source_path,
            original_filename=original_filename,
        ))


def get_external_candidate_service(db: Session) -> ExternalCandidateService:
    return ExternalCandidateService(db)
