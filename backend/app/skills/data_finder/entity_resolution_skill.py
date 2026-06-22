"""Entity 跨表对齐 Skill — VFL/多表 join 匹配率"""
from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import normalize_col


ENTITY_COLUMN_HINTS = (
    "entity_id", "client_id", "party_id", "sample_id", "patient_id",
    "subject_id", "user_id", "id",
)


class EntityResolutionSkill(BaseSkill):
    name = "EntityResolution"
    description = "检测多表 entity 列并对齐匹配率"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        tables = input_data.get("tables", []) or []
        alignments = input_data.get("alignments", []) or []

        if len(tables) < 2:
            result.data = {
                "skipped": True,
                "reason": "单表无需 entity 对齐",
                "match_rate": 1.0,
            }
            return result

        align_by_id = {a.get("table_id"): a for a in alignments if a.get("table_id")}
        entity_sets: List[Dict[str, Any]] = []

        for tbl in tables:
            csv_path = tbl.get("csv_path")
            if not csv_path or not os.path.exists(csv_path):
                continue
            cols = tbl.get("columns") or []
            entity_col = self._pick_entity_column(cols, align_by_id.get(tbl.get("table_id"), {}))
            if not entity_col:
                continue
            ids = self._read_entity_ids(csv_path, entity_col)
            if ids:
                entity_sets.append({
                    "table_id": tbl.get("table_id"),
                    "entity_column": entity_col,
                    "entity_count": len(ids),
                    "sample_ids": list(ids)[:5],
                })

        if len(entity_sets) < 2:
            result.data = {
                "skipped": True,
                "reason": "未检测到可对齐的 entity 列",
                "entity_columns_found": [e.get("entity_column") for e in entity_sets],
            }
            return result

        match_rate, unmatched_samples = self._compute_match_rate(entity_sets, tables)
        result.data = {
            "skipped": False,
            "entity_sets": entity_sets,
            "match_rate": round(match_rate, 4),
            "unmatched_samples": unmatched_samples[:10],
            "alignment_warnings": [] if match_rate >= 0.5 else [
                f"跨表 entity 匹配率仅 {match_rate:.0%}，合并结果可能不可靠"
            ],
        }
        if match_rate < 0.5:
            result.add_warning(f"Entity 匹配率 {match_rate:.0%} 偏低")
        return result

    @staticmethod
    def _pick_entity_column(columns: List[str], alignment: Dict[str, Any]) -> str:
        mapping = alignment.get("mapping") or {}
        std_cols = set(alignment.get("standard_columns") or [])
        for hint in ENTITY_COLUMN_HINTS:
            for col in columns:
                if normalize_col(col) == hint or col in std_cols and hint in normalize_col(col):
                    return col
            for orig, std in mapping.items():
                if normalize_col(std) == hint or hint in normalize_col(orig):
                    return orig
        for col in columns:
            nl = normalize_col(col)
            if nl.endswith("_id") or nl == "id":
                return col
        return ""

    @staticmethod
    def _read_entity_ids(csv_path: str, entity_col: str) -> Set[str]:
        ids: Set[str] = set()
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                val = (row.get(entity_col) or "").strip()
                if val:
                    ids.add(val)
        return ids

    @staticmethod
    def _compute_match_rate(
        entity_sets: List[Dict[str, Any]],
        tables: List[Dict[str, Any]],
    ) -> tuple:
        align_by_id = {t.get("table_id"): t for t in tables if t.get("table_id")}
        all_id_lists: List[Set[str]] = []
        for es in entity_sets:
            tbl = align_by_id.get(es["table_id"], {})
            path = tbl.get("csv_path")
            col = es["entity_column"]
            if path:
                all_id_lists.append(EntityResolutionSkill._read_entity_ids(path, col))

        if len(all_id_lists) < 2:
            return 1.0, []

        base = all_id_lists[0]
        if not base:
            return 0.0, []
        intersection = base
        for other in all_id_lists[1:]:
            intersection = intersection & other
        match_rate = len(intersection) / max(len(base), 1)
        unmatched = list(base - intersection)[:10]
        return match_rate, unmatched
