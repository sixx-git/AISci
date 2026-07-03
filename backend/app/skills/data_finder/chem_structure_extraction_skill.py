"""化学结构文件抽取 — SDF / MOL / SMILES（含 .gz）"""
from __future__ import annotations

import csv
import gzip
import os
import re
from typing import Any, Dict, Iterator, List, Optional, TextIO

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id
from app.skills.data_finder.file_format_registry import detect_file_format, is_chemistry_format

DEFAULT_MAX_RECORDS = 50_000

_PROP_HEADER_RE = re.compile(r"^>\s*<([^>]+)>\s*$")


def _open_text_source(file_path: str, filename: str) -> TextIO:
    fmt = detect_file_format(filename or os.path.basename(file_path))
    if fmt.endswith("_gz") or file_path.lower().endswith(".gz"):
        return gzip.open(file_path, "rt", encoding="utf-8", errors="replace")
    return open(file_path, "r", encoding="utf-8", errors="replace")


def _parse_sdf_properties(lines: List[str]) -> Dict[str, str]:
    props: Dict[str, str] = {}
    current_key: Optional[str] = None
    buf: List[str] = []
    in_props = False

    for line in lines:
        stripped = line.rstrip("\n\r")
        if stripped == "M  END":
            in_props = True
            continue
        if not in_props:
            continue
        m = _PROP_HEADER_RE.match(stripped)
        if m:
            if current_key is not None:
                props[current_key] = "\n".join(buf).strip()
            current_key = m.group(1).strip()
            buf = []
            continue
        if current_key is not None:
            if stripped == "$$$$":
                break
            buf.append(stripped)
    if current_key is not None:
        props[current_key] = "\n".join(buf).strip()
    return props


def _record_from_sdf_block(lines: List[str]) -> Dict[str, str]:
    title = (lines[0].strip() if lines else "") or ""
    props = _parse_sdf_properties(lines)
    row: Dict[str, str] = {"record_id": title}
    row.update({k: v for k, v in props.items()})
    if "chembl_id" not in row and title.upper().startswith("CHEMBL"):
        row["chembl_id"] = title.strip()
    for key in ("canonical_smiles", "smiles", "SMILES", "canonical_smiles_rdkit"):
        if key in row and "smiles" not in row:
            row["smiles"] = row[key]
            break
    return row


def _iter_sdf_records(handle: TextIO) -> Iterator[Dict[str, str]]:
    block: List[str] = []
    for line in handle:
        if line.rstrip("\n\r") == "$$$$":
            if block:
                yield _record_from_sdf_block(block)
            block = []
            continue
        block.append(line)
    if block:
        yield _record_from_sdf_block(block)


def _parse_smiles_line(line: str) -> Optional[Dict[str, str]]:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    parts = raw.split()
    if len(parts) == 1:
        return {"smiles": parts[0], "record_id": parts[0][:32]}
    if len(parts) == 2:
        return {"smiles": parts[0], "record_id": parts[1], "name": parts[1]}
    return {
        "smiles": parts[0],
        "record_id": parts[-1],
        "name": " ".join(parts[1:-1]) if len(parts) > 2 else parts[1],
    }


def _iter_smiles_records(handle: TextIO) -> Iterator[Dict[str, str]]:
    for line in handle:
        row = _parse_smiles_line(line)
        if row:
            yield row


class ChemStructureExtractionSkill(BaseSkill):
    name = "ChemStructureExtraction"
    description = "从 SDF/MOL/SMILES 化学结构文件抽取分子属性表（支持 ChEMBL .sdf.gz）"
    source_reference = "MDL SDF/MOL; ChEMBL compound exports"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        file_path = input_data.get("file_path", "")
        source_title = input_data.get("source_title", "")
        output_dir = input_data.get("output_dir", "")
        max_records = int(input_data.get("max_records") or DEFAULT_MAX_RECORDS)
        filename = input_data.get("filename") or os.path.basename(file_path)

        if not file_path or not os.path.exists(file_path):
            result.add_error("文件不存在")
            result.data = {"tables": []}
            return result

        if not is_chemistry_format(filename):
            result.add_warning(f"非化学结构格式: {filename}")
            result.data = {"tables": []}
            return result

        fmt = detect_file_format(filename)
        rows: List[Dict[str, str]] = []
        truncated = False

        try:
            with _open_text_source(file_path, filename) as handle:
                if fmt in ("smi", "smiles", "smi_gz", "smiles_gz"):
                    iterator: Iterator[Dict[str, str]] = _iter_smiles_records(handle)
                else:
                    iterator = _iter_sdf_records(handle)

                for row in iterator:
                    rows.append(row)
                    if len(rows) >= max_records:
                        truncated = True
                        break
        except Exception as exc:
            result.add_error(str(exc))
            result.data = {"tables": [], "errors": [str(exc)]}
            return result

        if not rows:
            result.add_error("未能从化学结构文件中解析出任何分子记录")
            result.data = {"tables": []}
            return result

        columns = list(dict.fromkeys(col for row in rows for col in row.keys()))
        table_id = new_id("tbl")
        out_dir = output_dir or os.path.dirname(file_path)
        os.makedirs(out_dir, exist_ok=True)
        csv_path = os.path.join(out_dir, f"{table_id}.csv")

        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        if truncated:
            result.add_warning(
                f"化学结构文件较大，已抽取前 {max_records} 条记录（可在上传时调整 max_records）"
            )

        result.data = {
            "tables": [{
                "table_id": table_id,
                "source_title": source_title,
                "caption": os.path.basename(filename),
                "csv_path": csv_path,
                "columns": columns,
                "row_count": len(rows),
                "quality_score": min(1.0, 0.55 + 0.05 * len(columns)),
                "extraction_method": "chem_structure",
                "source_type": "chem_structure",
                "truncated": truncated,
                "format": fmt,
            }],
        }
        return result
