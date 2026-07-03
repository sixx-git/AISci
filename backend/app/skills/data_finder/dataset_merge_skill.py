"""多源数据集合并 Skill — stack / join"""
from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id


def _package_row_provenance(row_provenance: List[Dict[str, Any]]) -> Any:
    if len(row_provenance) <= 200:
        return row_provenance
    return {"count": len(row_provenance), "sample": row_provenance[:50]}


class DatasetMergeSkill(BaseSkill):
    name = "DatasetMerge"
    description = "合并对齐后的 CSV（纵向 stack 或按 key join）并附加 provenance"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        tables = input_data.get("tables", []) or []
        alignments = input_data.get("alignments", []) or []
        provenance = input_data.get("provenance", []) or []
        output_dir = input_data.get("output_dir", "")
        merge_strategy = input_data.get("merge_strategy", "auto")

        if not tables:
            result.add_warning("无可合并表格")
            result.data = {"merged_csv_path": "", "row_count": 0}
            return result

        if merge_strategy == "auto":
            merge_strategy = self._infer_strategy(alignments)

        if merge_strategy == "join" and len(tables) >= 2:
            return await self._merge_join(tables, alignments, provenance, output_dir, result)

        return await self._merge_stack(tables, alignments, provenance, output_dir, result)

    @staticmethod
    def _infer_strategy(alignments: List[Dict[str, Any]]) -> str:
        join_keys: Set[str] = set()
        for a in alignments:
            for k in a.get("join_keys") or []:
                join_keys.add(k)
        if join_keys and len(alignments) >= 2:
            return "join"
        return "stack"

    async def _merge_stack(
        self,
        tables: List[Dict[str, Any]],
        alignments: List[Dict[str, Any]],
        provenance: List[Dict[str, Any]],
        output_dir: str,
        result: SkillResult,
    ) -> SkillResult:
        os.makedirs(output_dir, exist_ok=True)
        merge_id = new_id("merged")
        merged_path = os.path.join(output_dir, f"{merge_id}.csv")

        align_by_id = {a.get("table_id"): a for a in alignments if a.get("table_id")}
        prov_by_id = {p.get("record_id"): p for p in provenance if p.get("record_id")}

        all_rows: List[Dict[str, str]] = []
        all_columns: List[str] = []
        row_provenance: List[Dict[str, Any]] = []

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
                for row_idx, row in enumerate(reader, start=1):
                    out_row: Dict[str, str] = {}
                    for orig, val in row.items():
                        std = mapping.get(orig, orig)
                        out_row[std] = val
                    table_row_id = f"{table_id}_row_{row_idx}"
                    data_citation_id = new_id("cite")
                    out_row["_provenance_source_title"] = prov.get("source_title") or tbl.get("source_title", "")
                    out_row["_provenance_paper_id"] = prov.get("paper_id") or tbl.get("paper_id", "")
                    out_row["_provenance_page"] = str(prov.get("page") or tbl.get("page") or "")
                    out_row["_provenance_table_id"] = table_id
                    out_row["_provenance_extraction_method"] = prov.get("extraction_method") or tbl.get("extraction_method", "")
                    out_row["_table_row_id"] = table_row_id
                    out_row["_data_citation_id"] = data_citation_id
                    row_provenance.append({
                        "table_row_id": table_row_id,
                        "data_citation_id": data_citation_id,
                        "record_id": table_id,
                        "table_id": table_id,
                        "row_index": row_idx,
                        "source_title": out_row["_provenance_source_title"],
                        "paper_id": out_row["_provenance_paper_id"],
                        "page": out_row["_provenance_page"],
                        "extraction_method": out_row["_provenance_extraction_method"],
                        "source_type": tbl.get("source_type", "paper_table_row"),
                    })
                    all_rows.append(out_row)
                    for k in out_row:
                        if k not in all_columns:
                            all_columns.append(k)

        if not all_rows:
            result.add_warning("合并后无有效行，未编造数据")
            result.data = {"merged_csv_path": "", "row_count": 0, "merge_strategy": "stack"}
            return result

        with open(merged_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_columns)
            writer.writeheader()
            writer.writerows(all_rows)

        prov_out: Any = _package_row_provenance(row_provenance)

        result.data = {
            "merge_id": merge_id,
            "merged_csv_path": merged_path,
            "row_count": len(all_rows),
            "columns": all_columns,
            "row_provenance": prov_out,
            "merge_strategy": "stack",
        }
        return result

    async def _merge_join(
        self,
        tables: List[Dict[str, Any]],
        alignments: List[Dict[str, Any]],
        provenance: List[Dict[str, Any]],
        output_dir: str,
        result: SkillResult,
    ) -> SkillResult:
        align_by_id = {a.get("table_id"): a for a in alignments if a.get("table_id")}
        join_keys = []
        for a in alignments:
            for k in a.get("join_keys") or []:
                if k not in join_keys:
                    join_keys.append(k)
        if not join_keys:
            result.add_warning("join 模式缺少 join_keys，降级为 stack")
            return await self._merge_stack(tables, alignments, provenance, output_dir, result)

        primary_key = join_keys[0]
        merged_rows: Dict[str, Dict[str, str]] = {}
        all_columns: List[str] = []
        row_provenance: List[Dict[str, Any]] = []
        table_index = 0

        for tbl in tables:
            csv_path = tbl.get("csv_path")
            if not csv_path or not os.path.exists(csv_path):
                continue
            table_id = tbl.get("table_id", "")
            alignment = align_by_id.get(table_id, {})
            mapping = alignment.get("mapping") or {}
            suffix = f"_t{table_index}" if table_index > 0 else ""

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=1):
                    out_row: Dict[str, str] = {}
                    for orig, val in row.items():
                        std = mapping.get(orig, orig)
                        col = std if std == primary_key or table_index == 0 else f"{std}{suffix}"
                        out_row[col] = val

                    key_val = out_row.get(primary_key, "").strip()
                    if not key_val:
                        continue

                    if key_val not in merged_rows:
                        merged_rows[key_val] = dict(out_row)
                        merged_rows[key_val]["_merge_key"] = key_val
                    else:
                        for k, v in out_row.items():
                            if k == primary_key:
                                continue
                            merged_rows[key_val][k] = v

                    for k in merged_rows[key_val]:
                        if k not in all_columns:
                            all_columns.append(k)

                    if table_index == 0:
                        row_provenance.append({
                            "table_row_id": f"{table_id}_row_{row_idx}",
                            "data_citation_id": new_id("cite"),
                            "table_id": table_id,
                            "merge_key": key_val,
                            "source_type": "join_merge",
                        })
            table_index += 1

        if not merged_rows:
            result.add_warning("join 合并无有效行")
            result.data = {"merged_csv_path": "", "row_count": 0, "merge_strategy": "join"}
            return result

        os.makedirs(output_dir, exist_ok=True)
        merge_id = new_id("merged")
        merged_path = os.path.join(output_dir, f"{merge_id}.csv")
        if "_merge_key" not in all_columns:
            all_columns.insert(0, "_merge_key")

        with open(merged_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_columns)
            writer.writeheader()
            for row in merged_rows.values():
                writer.writerow({c: row.get(c, "") for c in all_columns})

        result.data = {
            "merge_id": merge_id,
            "merged_csv_path": merged_path,
            "row_count": len(merged_rows),
            "columns": all_columns,
            "row_provenance": _package_row_provenance(row_provenance),
            "merge_strategy": "join",
            "join_keys": join_keys,
        }
        return result
