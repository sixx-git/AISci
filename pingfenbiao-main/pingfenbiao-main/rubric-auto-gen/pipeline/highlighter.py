"""
PDF 高亮标注模块 — 在源 PDF 上标注与评分项关联的关键段落。

输出:
  - S1_highlighted.pdf 等标注版 PDF
  - source_notes.md 源文献笔记摘要
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llm_utils import call_llm_json
from .source_parser import SourceDocument

logger = logging.getLogger(__name__)


# ── Prompt 模板 ──────────────────────────────────────────────────────────

PROMPT_IDENTIFY_PASSAGES = """\
You are an expert academic literature analyst. Identify key passages from the source document that are relevant to each rubric item.

**Source ID**: {source_id}
**Document Content** (may be truncated):
---
{text}
---

**Rubric Items to Match**:
{rubric_items_text}

For each rubric item, find the most relevant passages in the document. Output as JSON array:
[
  {{
    "rubric_id": "R1",
    "passages": [
      {{
        "text": "Exact original text fragment (50-200 words)",
        "page": 3,
        "relevance": "high | medium"
      }}
    ]
  }}
]

Rules:
1. The "text" in passages must be exact copies from the document.
2. Only include highly relevant passages.
3. If a rubric item cannot be matched in the document, return an empty passages array.
4. Extract at most 3 passages per rubric item.
5. Pay special attention to passages supporting: definitions, mechanisms, data findings, limitations, and cross-source comparisons.

Output JSON array only.
"""

PROMPT_GENERATE_SOURCE_NOTES = """\
You are an expert academic literature analyst. Generate structured reading notes for the following document.

**Source ID**: {source_id}
**File Name**: {file_name}

**Document Content** (may be truncated):
---
{text}
---

**Related Rubric Items**:
{rubric_items_text}

Generate Markdown-formatted reading notes with:
1. **Document Overview**: 1-2 sentences summarizing the topic and core contribution
2. **Key Findings**: List 5-8 key findings or claims from the document
3. **Connection to Rubric Items**: Explain which rubric items this source supports (cite rubric_id)
4. **Key Quotations**: Extract the most important original text passages (with page numbers if available)

Output Markdown text directly.
"""


class Highlighter:
    """PDF 高亮标注器。"""

    def __init__(self, config):
        self.config = config
        self.client = config.get_client()

    def process_sources(self, sources: List[SourceDocument],
                        rubric_data: Dict[str, Any],
                        output_dir: str) -> None:
        """
        处理所有源文档：
        1. 识别与评分项关联的关键段落
        2. 在 PDF 上添加高亮标注
        3. 生成 source_notes.md
        """
        output_path = Path(output_dir) / "sources"
        output_path.mkdir(parents=True, exist_ok=True)

        # 收集所有评分项
        all_items = []
        for dim in rubric_data["rubrics"]["dimensions"]:
            all_items.extend(dim["items"])

        all_notes = []

        for source in sources:
            logger.info(f"  处理 {source.source_id} ({source.file_name})...")

            # 筛选与该来源相关的评分项
            related_items = [
                item for item in all_items
                if source.source_id in item.get("source_ids", [])
            ]

            if not related_items:
                logger.info(f"    无关联评分项，跳过")
                continue

            # 识别关键段落
            passages = self._identify_passages(source, related_items)

            # 高亮 PDF
            if source.file_type == "pdf":
                highlighted_path = output_path / f"{source.source_id}_highlighted.pdf"
                self._highlight_pdf(source.file_path, passages, str(highlighted_path))

            # 生成阅读笔记
            notes = self._generate_source_notes(source, related_items)
            all_notes.append(notes)

        # 合并所有笔记到 source_notes.md
        notes_path = output_path / "source_notes.md"
        notes_path.write_text(
            "\n\n---\n\n".join(all_notes),
            encoding="utf-8"
        )
        logger.info(f"  源文献笔记已保存到 {notes_path}")

    def _identify_passages(self, source: SourceDocument,
                           items: list) -> List[Dict]:
        """从源文档中识别与评分项相关的关键段落。"""
        items_text = "\n".join(
            f"  {it['rubric_id']}: {it['question']}"
            for it in items
        )

        prompt = PROMPT_IDENTIFY_PASSAGES.format(
            source_id=source.source_id,
            text=source.get_summary_for_llm(max_chars=12000),
            rubric_items_text=items_text,
        )

        try:
            result = call_llm_json(
                self.client,
                self.config.extract_model,
                prompt,
                system="You are a literature analysis expert. Precisely match rubric items with document passages.",
                temperature=0.2,
                max_retries=self.config.max_retries,
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"段落识别失败: {e}")
            return []

    def _highlight_pdf(self, pdf_path: str, passages: List[Dict],
                       output_path: str) -> bool:
        """在 PDF 上添加高亮标注。"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF 未安装，跳过 PDF 高亮")
            return False

        try:
            doc = fitz.open(pdf_path)

            # 收集所有需要高亮的文本片段
            highlight_texts = []
            for passage_group in passages:
                for passage in passage_group.get("passages", []):
                    text = passage.get("text", "")
                    page_hint = passage.get("page", 0)
                    if text and len(text) > 10:
                        highlight_texts.append((text, page_hint))

            # 在 PDF 中搜索并高亮
            highlight_count = 0
            for text, page_hint in highlight_texts:
                # 尝试在提示页码附近搜索
                search_pages = []
                if 0 < page_hint <= len(doc):
                    search_pages.append(page_hint - 1)
                # 如果提示页没找到，搜索所有页
                search_pages.extend(range(len(doc)))
                search_pages = list(dict.fromkeys(search_pages))  # 去重保序

                for page_idx in search_pages:
                    page = doc[page_idx]
                    # 搜索文本（取前 100 字符作为搜索关键词以提高命中率）
                    search_text = text[:100].strip()
                    text_instances = page.search_for(search_text)

                    for inst in text_instances:
                        # 添加高亮标注（黄色）
                        highlight = page.add_highlight_annot(inst)
                        highlight.set_colors(stroke=(1, 1, 0))  # 黄色
                        highlight.update()
                        highlight_count += 1
                        break  # 每段只高亮第一个匹配

                    if text_instances:
                        break  # 找到就不再搜索其他页

            doc.save(output_path)
            doc.close()
            logger.info(f"    PDF 高亮完成: {highlight_count} 处标注 → {output_path}")
            return True

        except Exception as e:
            logger.error(f"    PDF 高亮失败: {e}")
            return False

    def _generate_source_notes(self, source: SourceDocument,
                               items: list) -> str:
        """生成源文献阅读笔记。"""
        items_text = "\n".join(
            f"  {it['rubric_id']}: {it['question']}"
            for it in items
        )

        prompt = PROMPT_GENERATE_SOURCE_NOTES.format(
            source_id=source.source_id,
            file_name=source.file_name,
            text=source.get_summary_for_llm(max_chars=12000),
            rubric_items_text=items_text,
        )

        try:
            from .llm_utils import call_llm
            result = call_llm(
                self.client,
                self.config.extract_model,
                prompt,
                system="You are an academic literature analysis expert. Generate structured reading notes.",
                temperature=0.3,
                max_retries=self.config.max_retries,
            )
            return f"# {source.source_id}: {source.file_name}\n\n{result}"
        except Exception as e:
            logger.error(f"    笔记生成失败: {e}")
            return f"# {source.source_id}: {source.file_name}\n\n*笔记生成失败: {e}*"
