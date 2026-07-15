"""
DOI / 标题提取模块 — 从 PDF 中自动提取 DOI、arXiv ID 或标题，用于后续元数据查询。

提取策略（按优先级）：
  1. PDF 元数据中的 DOI 字段
  2. 前 5 页文本中的 DOI 正则匹配
  3. 前 5 页文本中的 arXiv ID 匹配（arXiv:XXXX.XXXXX → 转为 DOI 查询）
  4. 第一页最大字号文本作为标题候选
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# DOI 正则（宽松匹配，覆盖常见格式）
_DOI_PATTERNS = [
    re.compile(r'(?:doi:\s*|DOI:\s*|https?://doi\.org/)(10\.\d{4,9}/[-._;()/:A-Z0-9a-z]+)', re.I),
    re.compile(r'(?:^|\s)(10\.\d{4,9}/[-._;()/:A-Z0-9a-z]+)', re.I),
]

# arXiv ID 正则（如 arXiv:2106.09685v2）
_ARXIV_PATTERN = re.compile(r'arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)', re.I)

# 标题提取辅助：常见标题前缀词（用于过滤非标题行）
_TITLE_NOISE = re.compile(
    r'^(abstract|introduction|acknowledgment|reference|appendix|table|figure|copyright|'
    r'submitted|received|published|arxiv[:\s]?\d|preprint|doi[:\s]|https?://)\b',
    re.I,
)

# 简单的 URL 清理
_CLEAN_TRAIL = re.compile(r'[.,;:)\]}\s]+$')


def extract_doi(pdf_path: str | Path, max_pages: int = 5) -> Optional[str]:
    """从 PDF 中提取 DOI。

    Returns:
        DOI 字符串（不含 doi.org/ 前缀），或 None。
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))

    # 策略 1：PDF 元数据
    meta_doi = (doc.metadata.get("doi") or "").strip()
    if meta_doi:
        meta_doi = _clean_doi(meta_doi)
        if meta_doi:
            logger.info("DOI found in PDF metadata: %s", meta_doi)
            return meta_doi

    # 策略 2：前几页文本正则匹配
    pages_to_scan = min(max_pages, len(doc))
    for page_num in range(pages_to_scan):
        text = doc[page_num].get_text("text")
        for pattern in _DOI_PATTERNS:
            match = pattern.search(text)
            if match:
                doi = _clean_doi(match.group(1) if match.lastindex else match.group())
                if doi:
                    logger.info("DOI found on page %d: %s", page_num + 1, doi)
                    return doi

    # 策略 2.5：arXiv ID 提取（arXiv 论文通常没有传统 DOI）
    for page_num in range(min(2, len(doc))):
        text = doc[page_num].get_text("text")
        match = _ARXIV_PATTERN.search(text)
        if match:
            arxiv_id = match.group(1)
            logger.info("arXiv ID found on page %d: %s", page_num + 1, arxiv_id)
            return f"arxiv:{arxiv_id}"  # 特殊前缀，后续转为 DOI 查询

    logger.info("No DOI found in PDF: %s", pdf_path)
    return None


def extract_title(pdf_path: str | Path) -> Optional[str]:
    """从 PDF 第一页提取最可能是标题的文本。

    策略优先级：
    1. 字号最大文本（过滤 arXiv header 和噪声行后）
    2. 纯文本方式：取 Abstract/Introduction 之前的行
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    if not doc:
        return None

    page = doc[0]
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])

    # ── 策略 1：字号最大文本 ──
    # 收集 (text, font_size, y_pos) 候选
    candidates: list[tuple[str, float, float]] = []
    title_font_sizes: list[float] = []

    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            y_pos = line.get("bbox", [0, 0, 0, 0])[1]
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                size = span.get("size", 0)
                if not text or len(text) < 5:
                    continue
                if _TITLE_NOISE.match(text):
                    continue
                if re.match(r'^arXiv:\d', text, re.I):
                    continue
                candidates.append((text, size, y_pos))
                title_font_sizes.append(size)

    if candidates and title_font_sizes:
        # 找到最大字号（取前 3 大的中位数，避免单个异常值）
        sorted_sizes = sorted(title_font_sizes, reverse=True)
        max_size = sorted_sizes[0]
        if len(sorted_sizes) > 2:
            max_size = sorted_sizes[min(2, len(sorted_sizes) // 3)]

        # 收集所有最大字号附近的候选
        big_spans = [(t, s, y) for t, s, y in candidates if s >= max_size * 0.95]
        if big_spans:
            # 按 y 坐标排序，合并相邻行
            big_spans.sort(key=lambda x: x[2])
            first_y = big_spans[0][2]
            title_parts = []
            for text, size, y in big_spans:
                # 只合并 y 坐标差距不超过 1.5 倍字号的行
                if y <= first_y + max_size * 1.5:
                    title_parts.append(text)
                else:
                    break
            title = " ".join(title_parts)
            title = re.sub(r'\s+', ' ', title).strip()
            if len(title) >= 10:
                return title[:300]

    # ── 策略 2：纯文本方式，跳过 arXiv header，取 Abstract 之前的行 ──
    full_text = page.get_text("text")
    lines = full_text.splitlines()
    title_lines = []
    past_header = False  # 标记是否已跳过 arXiv header 区域
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if title_lines:
                continue
            else:
                continue
        # 检测 arXiv header 区域的结束
        if re.match(r'^arXiv:', stripped, re.I):
            past_header = True
            continue
        # 跳过 header 区域中的其他行（日期、分类等）
        if not past_header:
            continue
        if re.match(r'^(abstract|introduction)\b', stripped, re.I):
            break
        if re.match(r'^(doi|https?://)', stripped, re.I):
            continue
        # 跳过纯数字行（可能是页码或 arXiv ID）
        if re.match(r'^\d{4}\.\d{4,5}', stripped):
            continue
        if re.match(r'^\d$', stripped):
            continue
        title_lines.append(stripped)
        if len(title_lines) >= 6:
            break

    if title_lines:
        valid_lines = [l for l in title_lines if len(l) >= 5 and not re.match(r'^\d+$', l)]
        if valid_lines:
            title = " ".join(valid_lines)
            title = re.sub(r'\s+', ' ', title).strip()
            return title[:300]

    # ── fallback ──
    text = full_text.strip()
    first_lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 10]
    if first_lines:
        return first_lines[0][:200]
    return None


def extract_doi_and_title(pdf_path: str | Path) -> dict[str, Optional[str]]:
    """同时提取 DOI 和标题，返回 dict。"""
    doi = extract_doi(pdf_path)
    title = extract_title(pdf_path)
    return {"doi": doi, "title": title}


def _clean_doi(raw: str) -> Optional[str]:
    """清洗 DOI 字符串。"""
    # 去掉 doi.org 前缀
    doi = re.sub(r'^https?://doi\.org/', '', raw.strip())
    # 去掉末尾标点
    doi = _CLEAN_TRAIL.sub('', doi)
    # 验证基本格式
    if re.match(r'^10\.\d{4,9}/', doi):
        return doi
    return None
