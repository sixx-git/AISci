"""PDF 表格抽取 Skill"""
from __future__ import annotations

import csv
import os
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id


class PdfTableExtractionSkill(BaseSkill):
    name = "PdfTableExtraction"
    description = "从 PDF 抽取表格并导出 CSV，失败时不编造"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        file_path = input_data.get("file_path", "")
        paper_id = input_data.get("paper_id", "")
        source_title = input_data.get("source_title", "")
        output_dir = input_data.get("output_dir", "")
        tables_detected = input_data.get("tables_detected", []) or []

        if not file_path or not os.path.exists(file_path):
            result.add_error("PDF 文件不存在，无法抽取表格")
            result.data = {"tables": [], "errors": ["file_not_found"]}
            return result

        if not output_dir:
            result.add_error("未指定 output_dir")
            return result

        os.makedirs(output_dir, exist_ok=True)
        extracted: List[Dict[str, Any]] = []
        errors: List[str] = []

        try:
            tables = self._extract_with_pymupdf(file_path)
        except Exception as exc:
            errors.append(f"pymupdf: {exc}")
            tables = []

        if not tables:
            try:
                tables = self._extract_with_pdfplumber(file_path)
            except Exception as exc:
                errors.append(f"pdfplumber: {exc}")

        if not tables:
            result.add_warning("未能从 PDF 抽取结构化表格，未编造数据")
            result.data = {"tables": [], "errors": errors or ["no_tables_found"]}
            return result

        for idx, item in enumerate(tables):
            table_id = new_id("tbl")
            page = item.get("page", 0)
            caption = ""
            if idx < len(tables_detected):
                td = tables_detected[idx]
                caption = td.get("caption") or f"Table {td.get('table_number', idx + 1)}"
            else:
                caption = item.get("caption") or f"Table page {page} #{idx + 1}"

            csv_path = os.path.join(output_dir, f"{table_id}.csv")
            columns = item.get("columns", [])
            rows = item.get("rows", [])
            quality = self._score_quality(columns, rows)

            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                if columns:
                    writer.writerow(columns)
                writer.writerows(rows)

            extracted.append({
                "table_id": table_id,
                "paper_id": paper_id,
                "source_title": source_title,
                "page": page,
                "caption": caption,
                "csv_path": csv_path,
                "columns": columns,
                "row_count": len(rows),
                "quality_score": quality,
                "needs_review": quality < 0.6 or len(columns) < 2,
                "extraction_method": item.get("method", "pymupdf"),
            })

        result.data = {"tables": extracted, "errors": errors}
        if not extracted:
            result.add_warning("表格抽取失败，未生成 CSV")
        return result

    @staticmethod
    def _extract_with_pymupdf(file_path: str) -> List[Dict[str, Any]]:
        import fitz

        out: List[Dict[str, Any]] = []
        doc = fitz.open(file_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                finder = page.find_tables()
                if not finder or not finder.tables:
                    continue
                for table in finder.tables:
                    data = table.extract()
                    if not data or len(data) < 2:
                        continue
                    header = [str(c or "").strip() for c in data[0]]
                    rows = [[str(c or "").strip() for c in row] for row in data[1:]]
                    if not any(header):
                        continue
                    out.append({
                        "page": page_num + 1,
                        "columns": header,
                        "rows": rows,
                        "method": "pymupdf_find_tables",
                    })
        finally:
            doc.close()
        return out

    @staticmethod
    def _extract_with_pdfplumber(file_path: str) -> List[Dict[str, Any]]:
        import pdfplumber

        out: List[Dict[str, Any]] = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = [str(c or "").strip() for c in table[0]]
                    rows = [[str(c or "").strip() for c in row] for row in table[1:]]
                    if not any(header):
                        continue
                    out.append({
                        "page": page_num,
                        "columns": header,
                        "rows": rows,
                        "method": "pdfplumber",
                    })
        return out

    @staticmethod
    def _score_quality(columns: List[str], rows: List[List[str]]) -> float:
        if not columns or len(columns) < 2:
            return 0.2
        if not rows:
            return 0.35
        non_empty = sum(1 for r in rows for c in r if str(c).strip())
        total = max(len(rows) * len(columns), 1)
        fill_rate = non_empty / total
        return round(min(1.0, 0.4 + fill_rate * 0.6), 4)
