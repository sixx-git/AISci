"""
BibTeX 手动导入解析器（纯标准库实现，无外部依赖）

支持功能：
- 解析一个或多个 BibTeX 条目（@article, @inproceedings, @misc 等）
- 提取 title / authors / year / journal / booktitle / doi / url / abstract
- 返回标准化文献元数据
- 不访问 Google Scholar，不下载 PDF
"""
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 支持的 BibTeX 条目类型
SUPPORTED_ENTRY_TYPES = {
    "article", "inproceedings", "conference", "incollection",
    "book", "techreport", "misc", "phdthesis", "mastersthesis",
    "unpublished", "proceedings",
}


@dataclass
class BibTexEntry:
    """单个 BibTeX 条目的标准化元数据"""
    cite_key: str = ""
    entry_type: str = "misc"
    title: str = ""
    authors: str = ""           # 用逗号 + 空格连接
    year: Optional[int] = None
    journal: Optional[str] = None
    booktitle: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    source_type: str = "google_scholar_import"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cite_key": self.cite_key,
            "entry_type": self.entry_type,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "booktitle": self.booktitle,
            "volume": self.volume,
            "number": self.number,
            "pages": self.pages,
            "publisher": self.publisher,
            "doi": self.doi,
            "url": self.url,
            "abstract": self.abstract,
            "source_type": self.source_type,
        }


class BibTexParseError(Exception):
    """BibTeX 解析错误"""
    pass


class BibTexImporter:
    """BibTeX 解析器（纯标准库，无外部依赖）"""

    # 条目正则：@type{ cite_key, fields }
    _ENTRY_RE = re.compile(
        r'@(\w+)\s*\{\s*([^,]+?)\s*,\s*(.+?)\s*\}\s*$',
        re.DOTALL | re.IGNORECASE,
    )

    # 字段正则：field_name = {value} 或 field_name = "value"
    _FIELD_RE = re.compile(
        r'(\w+)\s*=\s*[{"](.+?)[}"]\s*,?\s*$',
        re.DOTALL,
    )

    # 作者列表分隔
    _AUTHOR_SEP_RE = re.compile(r'\s+and\s+', re.IGNORECASE)

    def __init__(self, default_source_type: str = "google_scholar_import"):
        self.default_source_type = default_source_type

    def parse(self, bibtex_text: str) -> List[BibTexEntry]:
        """
        解析 BibTeX 文本，返回条目列表

        Args:
            bibtex_text: BibTeX 格式字符串

        Returns:
            List[BibTexEntry]: 解析后的条目列表

        Raises:
            BibTexParseError: 解析失败时抛出
        """
        if not bibtex_text or not bibtex_text.strip():
            raise BibTexParseError("BibTeX 文本为空")

        # 移除注释行
        lines = bibtex_text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('%') or stripped.startswith('//'):
                continue
            cleaned_lines.append(line)

        clean_text = '\n'.join(cleaned_lines).strip()

        # 尝试拆分多个条目
        entries: List[BibTexEntry] = []
        raw_entries = self._split_entries(clean_text)

        if not raw_entries:
            raise BibTexParseError("未找到有效的 BibTeX 条目。请确保文本以 @ 开头，例如 @article{...}")

        for raw in raw_entries:
            try:
                entry = self._parse_single(raw)
                entries.append(entry)
            except Exception as e:
                logger.warning(f"解析 BibTeX 条目失败: {e}")
                continue

        if not entries:
            raise BibTexParseError("未能成功解析任何 BibTeX 条目")

        return entries

    def _split_entries(self, text: str) -> List[str]:
        """
        将文本拆分为多个 @ 开头的条目
        """
        entries = []
        # 找到所有 @ 的位置
        positions = [m.start() for m in re.finditer(r'@\w+\s*\{', text)]

        for i, start in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(text)
            entry_text = text[start:end].strip()
            if entry_text:
                entries.append(entry_text)

        return entries

    def _parse_single(self, raw: str) -> BibTexEntry:
        """
        解析单个 BibTeX 条目
        """
        # 匹配 @type{cite_key, ...}
        m = self._ENTRY_RE.match(raw.replace('\n', ' ').replace('\r', ''))
        if not m:
            # 尝试更多宽松匹配：找到匹配的 } 结束
            m = self._loose_match(raw)

        if not m:
            raise BibTexParseError(f"无法解析条目格式: {raw[:80]}...")

        entry_type = m.group(1).lower()
        cite_key = m.group(2).strip()
        body = m.group(3).strip()

        # 确保 entry_type 有效
        if entry_type not in SUPPORTED_ENTRY_TYPES:
            logger.debug(f"不常见的条目类型: {entry_type}，按 misc 处理")
            entry_type = "misc"

        # 解析字段
        fields = self._parse_fields(body)
        entry = self._fields_to_entry(cite_key, entry_type, fields)
        return entry

    def _loose_match(self, raw: str):
        """
        宽松匹配：处理大括号嵌套或多行等情况
        """
        # 找到 @type{ 的位置
        header_match = re.match(r'@(\w+)\s*\{\s*([^,]+?)\s*,', raw, re.IGNORECASE)
        if not header_match:
            return None

        entry_type = header_match.group(1)
        cite_key = header_match.group(2).strip()
        body_start = header_match.end()

        # 从 body_start 开始找到匹配的最后一个 }
        depth = 1
        pos = body_start
        while pos < len(raw) and depth > 0:
            if raw[pos] == '{':
                depth += 1
            elif raw[pos] == '}':
                depth -= 1
            pos += 1

        body = raw[body_start:pos - 1].strip()

        # 构造匹配对象
        class LooseMatch:
            pass
        result = LooseMatch()
        result.group = lambda g: {1: entry_type, 2: cite_key}.get(g, body)
        return result

    def _parse_fields(self, body: str) -> Dict[str, str]:
        """
        解析字段部分
        """
        fields: Dict[str, str] = {}
        # 处理大括号嵌套的情况
        # 简化版：逐个字段匹配
        pos = 0
        while pos < len(body):
            m = re.match(r'\s*(\w+)\s*=\s*', body[pos:])
            if not m:
                # 跳过逗号和空格
                skipped = re.match(r'\s*[,;]\s*', body[pos:])
                if skipped:
                    pos += skipped.end()
                    continue
                pos += 1
                continue

            field_name = m.group(1).lower()
            pos += m.end()

            # 读取值：{...} 或 "..."
            if pos >= len(body):
                break

            value, consumed = self._read_braced_value(body[pos:])
            if consumed == 0:
                value, consumed = self._read_quoted_value(body[pos:])

            if consumed > 0:
                fields[field_name] = value
                pos += consumed

                # 跳过尾部逗号
                tail = re.match(r'\s*[,;]?\s*', body[pos:])
                if tail:
                    pos += tail.end()
            else:
                pos += 1

        return fields

    def _read_braced_value(self, s: str):
        """读取 {value} 格式的值，处理嵌套"""
        if not s or s[0] != '{':
            return '', 0
        depth = 0
        i = 0
        while i < len(s):
            if s[i] == '{':
                depth += 1
            elif s[i] == '}':
                depth -= 1
                if depth == 0:
                    return s[1:i], i + 1  # 不含外层的 { }
            i += 1
        return s[1:], len(s)  # 未找到匹配的 }

    def _read_quoted_value(self, s: str):
        """读取 "value" 格式的值"""
        if not s or s[0] != '"':
            return '', 0
        i = 1
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                i += 2
                continue
            if s[i] == '"':
                return s[1:i], i + 1
            i += 1
        return s[1:], len(s)

    def _fields_to_entry(
        self, cite_key: str, entry_type: str, fields: Dict[str, str]
    ) -> BibTexEntry:
        """
        将解析的字段映射为 BibTexEntry
        """
        # 提取 year
        year = None
        raw_year = fields.get('year', '')
        if raw_year:
            try:
                year = int(re.search(r'\d{4}', raw_year).group(0))
            except (ValueError, AttributeError):
                pass

        # 作者处理：BibTeX 用 " and " 分隔，转换为逗号分隔
        authors_raw = fields.get('author', '') or fields.get('authors', '')
        authors = self._normalize_authors(authors_raw)

        # journal / booktitle
        journal = fields.get('journal') or None
        booktitle = fields.get('booktitle') or None

        entry = BibTexEntry(
            cite_key=cite_key,
            entry_type=entry_type,
            title=self._clean_text(fields.get('title', '')),
            authors=authors,
            year=year,
            journal=self._clean_text(journal) if journal else None,
            booktitle=self._clean_text(booktitle) if booktitle else None,
            volume=fields.get('volume') or None,
            number=fields.get('number') or None,
            pages=fields.get('pages') or None,
            publisher=fields.get('publisher') or None,
            doi=fields.get('doi') or None,
            url=fields.get('url') or None,
            abstract=fields.get('abstract') or fields.get('note') or None,
            source_type=self.default_source_type,
        )

        return entry

    def _normalize_authors(self, raw: str) -> str:
        """
        标准化作者格式：BibTeX 的 " and " 分隔 → 逗号分隔
        同时尝试处理 "Last, First" 格式转为 "First Last"
        """
        if not raw:
            return ""
        # 按 " and " 分割
        parts = self._AUTHOR_SEP_RE.split(raw)
        authors = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # 检测 "Last, First" 格式
            if ',' in p:
                names = [n.strip() for n in p.split(',')]
                if len(names) >= 2:
                    p = ' '.join(reversed(names))
            authors.append(p)
        return ', '.join(authors)

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本：去除 LaTeX 特殊字符、多余空白"""
        if not text:
            return ""
        text = text.strip()
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除常见 LaTeX 命令（保留内容）
        text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\emph\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\\w+\s*', '', text)  # 移除其他 LaTeX 命令
        text = text.replace('{', '').replace('}', '')
        return text.strip()


def parse_bibtex(
    bibtex_text: str,
    source_type: str = "google_scholar_import",
) -> List[Dict[str, Any]]:
    """
    便捷函数：解析 BibTeX 并返回字典列表

    Args:
        bibtex_text: BibTeX 格式字符串
        source_type: 来源类型标记

    Returns:
        List[Dict]: BibTexEntry.to_dict() 列表

    Raises:
        BibTexParseError: 解析失败
    """
    importer = BibTexImporter(default_source_type=source_type)
    entries = importer.parse(bibtex_text)
    return [e.to_dict() for e in entries]