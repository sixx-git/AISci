"""多源数据集合并 Skill"""
from __future__ import annotations

import csv
import os
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id


class DatasetMergeSkill(BaseSkill):
    name = "DatasetMerge"
    description = "合并对齐后的 CSV 并附加 provenance 列"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        tables = input_data.get("tables", []) or []
        alignments = input_data.get("alignments", []) or []
        provenance = input_data.get("provenance", []) or []
        output_dir = input_data.get("output_dir", "")

        if not tables:
            result.add_warning("无可合并表格")
            result.data = {"merged_csv_path": "", "row_count": 0}
            return result

        os.makedirs(output_dir, exist_ok=True)
        merge_id = new_id("merged")
        merged_path = os.path.join(output_dir, f"{merge_id}.csv")

        align_by_id = {a.get("table_id"): a for a in alignments if a.get("table_id")}
        prov_by_id = {p.get("record_id"): p for p in provenance if p.get("record_id")}

        all_rows: List[Dict[str, str]] = []
        all_columns: List[str] = []

        for tbl in tables:
            csv_path = tbl.get("csv_path")
            if not csv_path or not os.path.exists(csv_path):
                continue
            table_id = tbl.get("table_id", "")
            alignment = align_by_id.get(table_id, {})
            mapping = alignment.get("mapping") or {}
            prov = prov_by_id.get(table_id, {})

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    out_row: Dict[str, str] = {}
                    for orig, val in row.items():
                        std = mapping.get(orig, orig)
                        out_row[std] = val
                    out_row["_provenance_source_title"] = prov.get("source_title") or tbl.get("source_title", "")
                    out_row["_provenance_paper_id"] = prov.get("paper_id") or tbl.get("paper_id", "")
                    out_row["_provenance_page"] = str(prov.get("page") or tbl.get("page") or "")
                    out_row["_provenance_table_id"] = table_id
                    out_row["_provenance_extraction_method"] = prov.get("extraction_method") or tbl.get("extraction_method", "")
                    all_rows.append(out_row)
                    for k in out_row:
                        if k not in all_columns:
                            all_columns.append(k)

        if not all_rows:
            result.add_warning("合并后无有效行，未编造数据")
            result.data = {"merged_csv_path": "", "row_count": 0}
            return result

        with open(merged_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_columns)
            writer.writeheader()
            writer.writerows(all_rows)

        result.data = {
            "merge_id": merge_id,
            "merged_csv_path": merged_path,
            "row_count": len(all_rows),
            "columns": all_columns,
        }
        return result
