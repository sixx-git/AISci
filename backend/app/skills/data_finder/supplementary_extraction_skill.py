"""补充材料解析 Skill — 路由到 PDF 表格 / 通用表格文件"""
from __future__ import annotations

import os
import zipfile
from typing import Any, Dict, List

from app.services.data_sources.repository_connector import ALLOWED_EXTENSIONS
from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder.pdf_table_extraction_skill import PdfTableExtractionSkill
from app.skills.data_finder.tabular_file_extraction_skill import TabularFileExtractionSkill


class SupplementaryExtractionSkill(BaseSkill):
    name = "SupplementaryExtraction"
    description = "解析已下载的补充材料为表格 CSV"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        files = input_data.get("files", []) or []
        output_dir = input_data.get("output_dir", "")
        source_title = input_data.get("source_title", "Supplementary")

        tables: List[Dict[str, Any]] = []
        os.makedirs(output_dir, exist_ok=True)

        for finfo in files:
            path = finfo.get("local_path", "")
            paper_id = finfo.get("paper_id", "")
            if not path or not os.path.exists(path):
                continue
            ext = os.path.splitext(path)[1].lower()

            if ext == ".zip":
                tables.extend(await self._from_zip(path, output_dir, paper_id, source_title))
            elif ext == ".pdf":
                pdf_skill = PdfTableExtractionSkill()
                res = await pdf_skill.run(
                    {
                        "file_path": path,
                        "paper_id": paper_id,
                        "source_title": f"{source_title} (SI)",
                        "output_dir": output_dir,
                        "tables_detected": [],
                    },
                    context,
                )
                for tbl in res.data.get("tables", []):
                    tbl["source_type"] = "supplementary"
                    tbl["extraction_method"] = "supplementary_pdf"
                tables.extend(res.data.get("tables", []))
            elif ext in ALLOWED_EXTENSIONS or ext in {".csv", ".tsv", ".txt", ".xlsx", ".xls"}:
                tab_skill = TabularFileExtractionSkill()
                res = await tab_skill.run(
                    {"file_path": path, "source_title": f"{source_title} (SI)", "output_dir": output_dir},
                    context,
                )
                for tbl in res.data.get("tables", []):
                    tbl["paper_id"] = paper_id
                    tbl["source_type"] = "supplementary"
                    tbl["extraction_method"] = "supplementary_tabular"
                tables.extend(res.data.get("tables", []))

        result.data = {"tables": tables, "count": len(tables)}
        if files and not tables:
            result.add_warning("补充材料已下载但未能抽取表格")
        return result

    async def _from_zip(
        self,
        zip_path: str,
        output_dir: str,
        paper_id: str,
        source_title: str,
    ) -> List[Dict[str, Any]]:
        tables: List[Dict[str, Any]] = []
        tab_skill = TabularFileExtractionSkill()
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                ext = os.path.splitext(name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                extract_path = os.path.join(output_dir, os.path.basename(name))
                with zf.open(name) as src, open(extract_path, "wb") as dst:
                    dst.write(src.read(10 * 1024 * 1024))
                res = await tab_skill.run(
                    {"file_path": extract_path, "source_title": f"{source_title} (SI zip)", "output_dir": output_dir},
                    {},
                )
                for tbl in res.data.get("tables", []):
                    tbl["paper_id"] = paper_id
                    tbl["source_type"] = "supplementary"
                tables.extend(res.data.get("tables", []))
                if len(tables) >= 5:
                    break
        return tables
