"""图表人工复核 — 确认后写入 CSV 并纳入 merge"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.figure_extraction import write_figure_series_csv
from app.schemas.data_integration import build_figure_extraction_manifest
from app.skills.data_finder._utils import new_id

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class FigureReviewService:
    def __init__(self, db: Session):
        self.db = db
        from app.services.data_finder_service import get_data_finder_service

        self._df = get_data_finder_service(db)

    def review_figure(
        self,
        project_id: str,
        figure_id: str,
        *,
        action: str,
        edited_rows: Optional[List[Dict[str, Any]]] = None,
        reviewer_note: str = "",
    ) -> Dict[str, Any]:
        results = self._df.load_results(project_id) or {}
        figures = list(results.get("figures") or [])
        target = next((f for f in figures if f.get("figure_id") == figure_id), None)
        if not target:
            raise ValueError(f"未找到 figure_id={figure_id}")

        tables_dir = os.path.join(self._df._project_dir(project_id), "tables")
        os.makedirs(tables_dir, exist_ok=True)

        if action == "reject":
            target["review_status"] = "rejected"
            target["included_in_csv"] = False
            target["reviewer_note"] = reviewer_note
            target["reviewed_at"] = datetime.now(CHINA_TZ).isoformat()
        elif action in ("confirm", "confirm_edited"):
            rows = edited_rows or target.get("extracted_series_preview") or []
            if not rows:
                raise ValueError("无可确认的序列数据")
            csv_name = f"{figure_id}_series.csv"
            csv_path = os.path.join(tables_dir, csv_name)
            method = "manual" if action == "confirm_edited" else target.get("extraction_method", "rule")
            meta = {**target, "extraction_method": method, "extraction_confidence": 0.85}
            for row in rows:
                row["_provenance_extraction_method"] = method
            write_figure_series_csv(csv_path, rows, meta)

            target["review_status"] = "confirmed"
            target["included_in_csv"] = True
            target["extracted_series_csv_path"] = csv_path
            target["extraction_method"] = method
            target["extraction_confidence"] = 0.85
            target["needs_manual_review"] = False
            target["extraction_tier"] = "L4_confirmed"
            target["reviewer_note"] = reviewer_note
            target["reviewed_at"] = datetime.now(CHINA_TZ).isoformat()
            target["extraction_manifest"] = build_figure_extraction_manifest(target)

            table_id = target.get("table_id") or new_id("figtbl")
            target["table_id"] = table_id
            tables = list(results.get("extracted_tables") or [])
            tables = [t for t in tables if t.get("table_id") != table_id]
            import csv as csvmod

            columns: List[str] = []
            if os.path.exists(csv_path):
                with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csvmod.DictReader(f)
                    columns = list(reader.fieldnames or [])

            tables.append({
                "table_id": table_id,
                "paper_id": target.get("paper_id", ""),
                "source_title": target.get("source_title", ""),
                "page": 0,
                "caption": target.get("caption", ""),
                "csv_path": csv_path,
                "columns": columns,
                "quality_score": 0.85,
                "extraction_method": method,
                "source_type": "figure_series",
                "figure_id": figure_id,
            })
            results["extracted_tables"] = tables
            prov = list(results.get("provenance") or [])
            prov = [p for p in prov if p.get("record_id") != table_id]
            prov.append({
                "record_id": table_id,
                "source_type": "figure_series",
                "source_title": target.get("source_title", ""),
                "paper_id": target.get("paper_id", ""),
                "page": None,
                "table_or_figure": figure_id,
                "extraction_method": method,
                "confidence": 0.85,
            })
            results["provenance"] = prov
        else:
            raise ValueError(f"未知 action: {action}")

        for i, fig in enumerate(figures):
            if fig.get("figure_id") == figure_id:
                figures[i] = target
                break
        results["figures"] = figures
        self._df.save_results(project_id, results)

        remerge: Optional[Dict[str, Any]] = None
        if action in ("confirm", "confirm_edited"):
            asyncio.run(self._df.run_align_schema(project_id))
            merged_results = asyncio.run(self._df.run_merge(project_id))
            remerge = {
                "align_tables": len(merged_results.get("alignments") or []),
                "merged_rows": (merged_results.get("merged") or {}).get("row_count"),
                "merged_csv_path": (merged_results.get("merged") or {}).get("merged_csv_path"),
            }
            target = next(
                (f for f in (merged_results.get("figures") or figures) if f.get("figure_id") == figure_id),
                target,
            )

        response = dict(target)
        if remerge:
            response["remerge"] = remerge
        return response

    def get_paper_extraction_stats(self, project_id: str) -> Dict[str, Any]:
        results = self._df.load_results(project_id) or {}
        tables = results.get("extracted_tables") or []
        figures = results.get("figures") or []
        by_paper: Dict[str, Dict[str, int]] = {}

        for t in tables:
            pid = t.get("paper_id") or "unknown"
            by_paper.setdefault(pid, {"tables": 0, "figures_confirmed": 0, "figures_pending": 0})
            if t.get("source_type") == "figure_series":
                by_paper[pid]["figures_confirmed"] += 1
            else:
                by_paper[pid]["tables"] += 1

        for f in figures:
            pid = f.get("paper_id") or "unknown"
            by_paper.setdefault(pid, {"tables": 0, "figures_confirmed": 0, "figures_pending": 0})
            if f.get("included_in_csv"):
                pass
            elif f.get("needs_manual_review"):
                by_paper[pid]["figures_pending"] += 1

        return {
            "by_paper": by_paper,
            "total_tables": len([t for t in tables if t.get("source_type") != "figure_series"]),
            "total_figures": len(figures),
            "figures_pending_review": sum(1 for f in figures if f.get("needs_manual_review") and not f.get("included_in_csv")),
        }


def get_figure_review_service(db: Session) -> FigureReviewService:
    return FigureReviewService(db)
