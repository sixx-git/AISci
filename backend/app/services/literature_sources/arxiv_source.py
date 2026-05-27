"""
arXiv 文献搜索（通过官方 API，零额外依赖）

使用 arXiv Atom API：
  https://export.arxiv.org/api/query?search_query={query}&max_results={n}

返回标准化论文元数据，当前阶段不下载 PDF。
"""
import urllib.request
import urllib.parse
import urllib.error
import ssl
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# arXiv API 配置
ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_TIMEOUT = 30  # 秒（国内网络访问 arXiv 较慢，需更长超时）
ARXIV_NAMESPACES = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom',
}


@dataclass
class ArxivPaper:
    """标准化 arXiv 论文元数据"""
    title: str = ""
    authors: str = ""
    abstract: str = ""
    published_at: Optional[datetime] = None
    categories: str = ""
    external_id: str = ""          # arXiv ID，如 "2301.07041"
    source_url: str = ""           # https://arxiv.org/abs/{id}
    pdf_url: str = ""              # https://arxiv.org/pdf/{id}
    source_type: str = "arxiv"
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "categories": self.categories,
            "external_id": self.external_id,
            "source_url": self.source_url,
            "pdf_url": self.pdf_url,
            "source_type": self.source_type,
            "doi": self.doi,
            "journal_ref": self.journal_ref,
            "comment": self.comment,
        }


class ArxivSource:
    """arXiv 文献数据源（只检索元数据，不下载 PDF）"""

    def __init__(self, timeout: int = ARXIV_TIMEOUT, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries

    def search(
        self,
        query: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance",
    ) -> List[ArxivPaper]:
        """
        搜索 arXiv 文献

        Args:
            query: 搜索关键词（支持 arXiv 查询语法）
            max_results: 最大返回结果数（1-100）
            start: 起始偏移
            sort_by: 排序方式（relevance / lastUpdatedDate / submittedDate）

        Returns:
            List[ArxivPaper]: 标准化论文元数据列表
        """
        if not query or not query.strip():
            raise ValueError("查询关键词不能为空")

        max_results = max(1, min(max_results, 100))

        # 构建请求 URL
        params = {
            "search_query": query,
            "start": str(start),
            "max_results": str(max_results),
            "sortBy": sort_by,
        }
        url = f"{ARXIV_API_BASE}?{urllib.parse.urlencode(params)}"

        logger.info(f"arXiv search: query='{query}', max_results={max_results}")

        import time

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # 创建 SSL context
                ctx = ssl.create_default_context()
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as response:
                    raw_xml = response.read().decode("utf-8")

                papers = self._parse_atom_response(raw_xml)
                logger.info(f"arXiv search returned {len(papers)} results")
                return papers

            except urllib.error.URLError as e:
                reason = str(e.reason) if e.reason else "Unknown Error"
                last_error = RuntimeError(f"arXiv API 连接失败: {reason}")
                logger.warning(f"arXiv 网络错误 (attempt {attempt+1}/{self.max_retries+1}): {reason}")
            except ssl.SSLError as e:
                last_error = RuntimeError(f"arXiv SSL 验证失败（可能需要配置代理或 VPN）: {e}")
                logger.warning(f"arXiv SSL 错误 (attempt {attempt+1}/{self.max_retries+1}): {e}")
            except TimeoutError as e:
                last_error = RuntimeError(f"arXiv API 请求超时 ({self.timeout}秒，国内访问可能较慢)")
                logger.warning(f"arXiv 超时 (attempt {attempt+1}/{self.max_retries+1})")
            except ConnectionError as e:
                last_error = RuntimeError(f"arXiv API 连接被拒绝（请检查网络或代理设置）: {e}")
                logger.warning(f"arXiv 连接拒绝 (attempt {attempt+1}/{self.max_retries+1}): {e}")
            except ET.ParseError as e:
                # XML 解析错误不重试
                logger.error(f"arXiv API XML 解析失败: {e}")
                raise RuntimeError("arXiv 返回数据解析失败") from e
            except Exception as e:
                last_error = RuntimeError(f"arXiv 搜索异常 ({type(e).__name__}): {e}")
                logger.warning(f"arXiv 未知错误 (attempt {attempt+1}/{self.max_retries+1}): {type(e).__name__}: {e}")

            # 重试前等待
            if attempt < self.max_retries:
                wait = 2 * (attempt + 1)
                time.sleep(wait)

        # 所有重试均失败
        raise last_error or RuntimeError("arXiv API 连接失败（已重试）")

    def search_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """
        根据 arXiv ID 精确查询单篇论文

        Args:
            arxiv_id: arXiv ID（如 "2301.07041"）

        Returns:
            ArxivPaper or None
        """
        results = self.search(f"id:{arxiv_id}", max_results=1)
        return results[0] if results else None

    def _parse_atom_response(self, raw_xml: str) -> List[ArxivPaper]:
        """解析 arXiv Atom XML 响应"""
        root = ET.fromstring(raw_xml)
        entries = root.findall("atom:entry", ARXIV_NAMESPACES)

        papers = []
        for entry in entries:
            paper = self._parse_entry(entry)
            papers.append(paper)

        return papers

    def _parse_entry(self, entry: ET.Element) -> ArxivPaper:
        """解析单个 Atom entry"""
        ns = ARXIV_NAMESPACES

        # arXiv ID — 从 <id> 标签提取（格式: http://arxiv.org/abs/xxxx.xxxxx）
        id_url = self._text(entry, "atom:id", ns, "")
        arxiv_id = id_url.split("/abs/")[-1] if "/abs/" in id_url else ""

        # 标题 — 清理换行和多余空格
        title = self._text(entry, "atom:title", ns, "")
        title = " ".join(title.split())

        # 作者 — 逗号分隔
        author_names = []
        for author_elem in entry.findall("atom:author", ns):
            name = self._text(author_elem, "atom:name", ns, "")
            if name:
                author_names.append(name)
        authors = ", ".join(author_names)

        # 摘要 — 清理换行和多余空格
        abstract = self._text(entry, "atom:summary", ns, "")
        abstract = " ".join(abstract.split())

        # 发布日期
        published_str = self._text(entry, "atom:published", ns, "")
        published_at = None
        if published_str:
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # 分类
        categories_list = []
        for cat_elem in entry.findall("atom:category", ns):
            term = cat_elem.get("term", "")
            if term:
                categories_list.append(term)
        categories = ", ".join(categories_list)

        # DOI
        doi = None
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "doi":
                doi = link.get("href", "").strip()
                break

        # 期刊引用
        journal_ref = self._text(entry, "arxiv:journal_ref", ns, None)

        # 备注
        comment = self._text(entry, "arxiv:comment", ns, None)

        return ArxivPaper(
            title=title,
            authors=authors,
            abstract=abstract,
            published_at=published_at,
            categories=categories,
            external_id=arxiv_id,
            source_url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
            source_type="arxiv",
            doi=doi,
            journal_ref=journal_ref,
            comment=comment,
        )

    @staticmethod
    def _text(
        element: ET.Element,
        tag: str,
        namespaces: Dict[str, str],
        default: Optional[str] = ""
    ) -> Optional[str]:
        """安全提取 XML 子元素的文本内容"""
        child = element.find(tag, namespaces)
        if child is not None:
            return child.text or default
        return default