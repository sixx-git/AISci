"""外部数据候选 — 用户手动下载后上传并纳入 merge"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.skills.data_finder.file_format_registry import (
    collect_parseable_files,
    is_allowed_upload_filename,
)

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))

MANUAL_AVAILABILITY = frozenset({"catalog_only", "metadata_only", "url_only"})
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


def _collect_parseable_files(root_dir: str) -> List[str]:
    return collect_parseable_files(root_dir)


def _extract_zip_archive(zip_path: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # 防止 Zip Slip
            target = os.path.normpath(os.path.join(dest_dir, info.filename))
            if not target.startswith(os.path.normpath(dest_dir) + os.sep):
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return dest_dir


def _resolve_upload_targets(upload_dir: str, source_path: str, original_filename: str) -> Tuple[List[str], Optional[str]]:
    """返回待解析文件列表及 ZIP 解压目录（若有）。"""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext == ".zip":
        extract_dir = os.path.join(upload_dir, "extracted")
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
        _extract_zip_archive(source_path, extract_dir)
        files = _collect_parseable_files(extract_dir)
        if not files:
            raise ValueError("ZIP 内未找到可解析的 CSV/JSON/SDF/MOL/SMILES 等文件")
        return files, extract_dir
    return [source_path], None


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

        if not is_allowed_upload_filename(original_filename):
            raise ValueError(
                "不支持的上传格式，请使用 CSV/TSV/XLSX/JSON/ZIP/SDF/MOL/SMILES（含 .sdf.gz）"
            )

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
            from app.skills.data_finder.structured_file_extraction_skill import extract_tables_from_file

            tables_dir = os.path.join(self._df._project_dir(project_id), "tables")
            os.makedirs(tables_dir, exist_ok=True)
            parse_targets, extract_dir = _resolve_upload_targets(upload_dir, dest_path, original_filename)
            cand["user_upload_manifest"] = [os.path.relpath(p, upload_dir) for p in parse_targets[:20]]
            if extract_dir:
                cand["user_upload_extracted_dir"] = os.path.relpath(extract_dir, upload_dir)

            tbl = None
            last_err = "未能解析文件"
            for file_path in parse_targets:
                tables = await extract_tables_from_file(
                    file_path,
                    source_title=cand.get("dataset_name") or original_filename,
                    output_dir=tables_dir,
                    filename=os.path.basename(file_path),
                    context={"stage": "external_candidate_upload"},
                )
                if tables:
                    tbl = dict(tables[0])
                    tbl["source_file"] = os.path.relpath(file_path, upload_dir)
                    break
                last_err = "未能从该文件解析出表格数据"

            if not tbl:
                raise ValueError(str(last_err))
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
