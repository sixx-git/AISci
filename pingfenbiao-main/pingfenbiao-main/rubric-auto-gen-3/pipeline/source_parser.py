"""
源文件解析模块 — 从 PDF / CSV / Markdown 文件中提取结构化文本。

支持的文件类型：
  - PDF：使用 PyMuPDF 提取全文，按段落切分
  - CSV：读取表头 + 数据，生成结构化描述
  - Markdown：直接读取原文
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class TextBlock:
    """文本块 — 一段连续的文本内容。"""
    text: str
    page: int = 0          # 页码（PDF 适用）
    block_id: str = ""     # 块 ID

    def __len__(self):
        return len(self.text)


@dataclass
class SourceDocument:
    """源文档 — 一个输入文件的完整解析结果。"""
    source_id: str                 # S1, S2, F1 等
    file_name: str
    file_path: str
    file_type: str                 # pdf | csv | md
    description: str = ""
    blocks: List[TextBlock] = field(default_factory=list)
    full_text: str = ""
    page_count: int = 0

    @property
    def char_count(self) -> int:
        return len(self.full_text)

    def get_text_chunk(self, max_chars: int = 12000, offset: int = 0) -> str:
        """获取截断后的文本（用于 LLM 上下文窗口控制）。"""
        return self.full_text[offset:offset + max_chars]

    def get_summary_for_llm(self, max_chars: int = 16000) -> str:
        """生成适合发送给 LLM 的文本摘要。"""
        text = self.full_text
        if len(text) > max_chars:
            # 智能截断：保留开头和结尾
            head = max_chars * 2 // 3
            tail = max_chars // 3
            text = (
                text[:head]
                + f"\n\n... [中间省略约 {len(self.full_text) - head - tail} 字符] ...\n\n"
                + text[-tail:]
            )
        return text


class SourceParser:
    """源文件解析器。"""

    SUPPORTED_TYPES = {".pdf", ".csv", ".md", ".txt"}

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def parse_directory(self, source_dir: str) -> List[SourceDocument]:
        """解析目录下所有支持的文件，返回 SourceDocument 列表。"""
        source_dir = Path(source_dir)
        if not source_dir.exists():
            raise FileNotFoundError(f"源文件目录不存在: {source_dir}")

        documents = []
        source_idx = 1

        # 按文件名排序，确保顺序稳定
        files = sorted(source_dir.iterdir())
        for file_path in files:
            if file_path.suffix.lower() not in self.SUPPORTED_TYPES:
                continue

            source_id = f"S{source_idx}"
            doc = self.parse_file(str(file_path), source_id)
            documents.append(doc)
            source_idx += 1

            if self.verbose:
                print(f"  [解析] {source_id}: {file_path.name} "
                      f"({doc.file_type}, {doc.char_count} 字符, {doc.page_count} 页)")

        return documents

    def parse_file(self, file_path: str, source_id: str = "S1") -> SourceDocument:
        """解析单个文件。"""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._parse_pdf(path, source_id)
        elif ext == ".csv":
            return self._parse_csv(path, source_id)
        elif ext in (".md", ".txt"):
            return self._parse_text(path, source_id)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    def _parse_pdf(self, path: Path, source_id: str) -> SourceDocument:
        """解析 PDF 文件。"""
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        blocks = []
        full_text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                blocks.append(TextBlock(
                    text=text.strip(),
                    page=page_num + 1,
                    block_id=f"{source_id}_p{page_num + 1}",
                ))
                full_text_parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")

        page_count = len(doc)
        doc.close()

        return SourceDocument(
            source_id=source_id,
            file_name=path.name,
            file_path=str(path),
            file_type="pdf",
            description=f"PDF document, {page_count} pages",
            blocks=blocks,
            full_text="\n\n".join(full_text_parts),
            page_count=page_count,
        )

    def _parse_csv(self, path: Path, source_id: str) -> SourceDocument:
        """解析 CSV 文件。"""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        headers = reader.fieldnames or []

        # 生成结构化描述
        text_parts = [
            f"CSV File: {path.name}",
            f"Columns ({len(headers)}): {', '.join(headers)}",
            f"Rows: {len(rows)}",
            "",
            "=== Data Preview (first 50 rows) ===",
        ]

        if rows:
            # 表头
            text_parts.append(" | ".join(headers))
            text_parts.append("-" * 80)
            for i, row in enumerate(rows[:50]):
                text_parts.append(" | ".join(str(row.get(h, "")) for h in headers))

            if len(rows) > 50:
                text_parts.append(f"\n... ({len(rows) - 50} more rows)")

        # 基础统计
        text_parts.extend([
            "",
            "=== Basic Statistics ===",
        ])
        for header in headers:
            values = [row.get(header, "") for row in rows if row.get(header, "")]
            if values:
                try:
                    nums = [float(v) for v in values]
                    text_parts.append(
                        f"  {header}: min={min(nums):.4f}, max={max(nums):.4f}, "
                        f"mean={sum(nums)/len(nums):.4f}, count={len(nums)}"
                    )
                except (ValueError, TypeError):
                    unique = set(values)
                    text_parts.append(
                        f"  {header}: {len(unique)} unique values, "
                        f"sample={list(unique)[:5]}"
                    )

        full_text = "\n".join(text_parts)
        return SourceDocument(
            source_id=source_id,
            file_name=path.name,
            file_path=str(path),
            file_type="csv",
            description=f"CSV with {len(headers)} columns and {len(rows)} rows",
            blocks=[TextBlock(text=full_text, block_id=f"{source_id}_data")],
            full_text=full_text,
            page_count=1,
        )

    def _parse_text(self, path: Path, source_id: str) -> SourceDocument:
        """解析 Markdown / 纯文本文件。"""
        text = path.read_text(encoding="utf-8")
        return SourceDocument(
            source_id=source_id,
            file_name=path.name,
            file_path=str(path),
            file_type=path.suffix.lstrip("."),
            description=f"Text file, {len(text)} characters",
            blocks=[TextBlock(text=text, block_id=f"{source_id}_text")],
            full_text=text,
            page_count=1,
        )
