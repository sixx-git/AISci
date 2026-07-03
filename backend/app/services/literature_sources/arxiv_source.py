"""
arXiv 文献搜索（通过官方 API，零额外依赖）

使用 arXiv Atom API：
  https://export.arxiv.org/api/query?search_query={query}&max_results={n}

返回标准化论文元数据，当前阶段不下载 PDF。

降级策略（参考 SakanaAI/AI-Scientist）：
  1. arXiv 官方 API
  2. OpenAlex API（国内网络通常更稳定）
  3. 本地 JSON fallback 缓存
"""
import urllib.request
import urllib.parse
import urllib.error
import ssl
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

# arXiv API 配置
ARXIV_API_BASE = "https://export.arxiv.org/api/query"
OPENALEX_API_BASE = "https://api.openalex.org/works"
DEFAULT_USER_AGENT = "AISci/1.0 (+https://github.com/; research literature retrieval)"
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

    FALLBACK_WARNING = "arXiv API 当前不可访问，已使用本地演示文献缓存。"
    OPENALEX_WARNING = "arXiv API 当前不可访问，已通过 OpenAlex 检索相关论文（参考 AI-Scientist 文献检索降级策略）。"

    def __init__(
        self,
        timeout: int = 15,
        max_retries: int = 4,
        http_proxy: str = "",
        https_proxy: str = "",
        fallback_data_path: str = "./data/arxiv_fallback.json",
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.fallback_data_path = fallback_data_path
        self.user_agent = user_agent
        self.http_proxy = http_proxy
        self.https_proxy = https_proxy

        # 预加载 fallback 数据
        self._fallback_data: Optional[List[Dict[str, Any]]] = None

    def _resolve_fallback_path(self) -> str:
        path = self.fallback_data_path
        if os.path.isabs(path):
            return path
        backend_root = Path(__file__).resolve().parents[3]
        return str((backend_root / path.lstrip("./")).resolve())

    def _build_opener(self) -> urllib.request.OpenerDirector:
        """构建支持 SSL 与可选代理的 opener（urllib OpenerDirector.open 不支持 context 参数）"""
        ctx = ssl.create_default_context()
        handlers: List[Any] = [urllib.request.HTTPSHandler(context=ctx)]
        proxy_map: Dict[str, str] = {}
        if self.https_proxy:
            proxy_map["https"] = self.https_proxy
        if self.http_proxy:
            proxy_map["http"] = self.http_proxy
        if proxy_map:
            handlers.insert(0, urllib.request.ProxyHandler(proxy_map))
            logger.info(f"arXiv 使用代理: {proxy_map}")
        return urllib.request.build_opener(*handlers)

    def _fetch_text(self, url: str) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with self._build_opener().open(req, timeout=self.timeout) as response:
                    return response.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300]
                last_error = RuntimeError(f"HTTP {e.code}: {body}")
                if e.code in (429, 503) and attempt < self.max_retries:
                    delay = 5 * (2 ** attempt)
                    logger.warning("arXiv/OpenAlex HTTP %d，%ss 后重试 (%d/%d)", e.code, delay, attempt + 1, self.max_retries + 1)
                    time.sleep(delay)
                    continue
                raise last_error from e
            except (urllib.error.URLError, TimeoutError, ssl.SSLError) as e:
                last_error = RuntimeError(f"请求失败: {e}")
                if attempt < self.max_retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise last_error from e
        raise last_error or RuntimeError("HTTP 请求失败")

    def _load_fallback_data(self) -> List[Dict[str, Any]]:
        if self._fallback_data is not None:
            return self._fallback_data
        path = self._resolve_fallback_path()
        if not os.path.isfile(path):
            logger.warning(f"Fallback 数据文件不存在: {path}")
            self._fallback_data = []
            return self._fallback_data
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._fallback_data = json.load(f)
            logger.info(f"已加载 fallback 数据: {len(self._fallback_data)} 条")
        except Exception as e:
            logger.warning(f"Fallback 数据加载失败: {e}")
            self._fallback_data = []
        return self._fallback_data

    def _match_keywords(self, query: str, paper: Dict[str, Any]) -> int:
        query_lower = query.lower()
        score = 0
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        categories = (paper.get("categories") or "").lower()

        # 分词匹配
        tokens = query_lower.replace('"', '').replace("'", "").split()
        for token in tokens:
            token = token.strip().strip(".,;:!?()-")
            if not token:
                continue
            if token in title:
                score += 3
            if token in abstract:
                score += 1
            if token in categories:
                score += 2

        # 短语匹配加分
        if query_lower in title:
            score += 5
        if query_lower in abstract:
            score += 2

        return score

    def _search_fallback(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        data = self._load_fallback_data()
        if not data:
            return []

        scored = [(self._match_keywords(query, paper), paper) for paper in data]
        scored.sort(key=lambda x: x[0], reverse=True)

        results = [paper for score, paper in scored if score > 0]
        if not results:
            results = data[:max_results]
        return results[:max_results]

    def search_with_fallback(
        self,
        query: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance",
    ) -> Tuple[List[ArxivPaper], bool, str]:
        if not query or not query.strip():
            raise ValueError("查询关键词不能为空")

        max_results = max(1, min(max_results, 100))

        # 尝试真实 arXiv API
        try:
            papers = self.search(query, max_results, start, sort_by)
            return (papers, False, "")
        except Exception as e:
            logger.warning(f"arXiv 真实 API 失败: {e}")

        # OpenAlex 降级（AI-Scientist 推荐的文献检索替代源）
        try:
            openalex_papers = self._search_openalex(query, max_results)
            if openalex_papers:
                return (openalex_papers, True, self.OPENALEX_WARNING)
        except Exception as e:
            logger.warning(f"OpenAlex 降级检索失败: {e}")

        # 本地 JSON fallback
        try:
            fallback_results = self._search_fallback(query, max_results)
            if not fallback_results:
                raise RuntimeError("Fallback 数据为空，无法提供搜索结果。")

            papers = []
            for item in fallback_results:
                published_at = None
                if item.get("published_at"):
                    try:
                        published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                papers.append(ArxivPaper(
                    title=item.get("title", ""),
                    authors=item.get("authors", ""),
                    abstract=item.get("abstract", ""),
                    published_at=published_at,
                    categories=item.get("categories", ""),
                    external_id=item.get("external_id", ""),
                    source_url=item.get("source_url", ""),
                    pdf_url=item.get("pdf_url", ""),
                    source_type=item.get("source_type", "arxiv"),
                    doi=item.get("doi"),
                    journal_ref=item.get("journal_ref"),
                    comment=item.get("comment"),
                ))

            return (papers, True, self.FALLBACK_WARNING)
        except Exception as e2:
            raise RuntimeError(f"arXiv 搜索失败且 fallback 不可用: {e2}")

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

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                raw_xml = self._fetch_text(url)
                papers = self._parse_atom_response(raw_xml)
                logger.info(f"arXiv search returned {len(papers)} results")
                return papers

            except urllib.error.URLError as e:
                reason = str(e.reason) if e.reason else "Unknown Error"
                last_error = RuntimeError(f"arXiv API 连接失败: {reason}")
                logger.warning(f"arXiv 网络错误 (attempt {attempt+1}/{self.max_retries+1}): {reason}")
            except ssl.SSLError as e:
                last_error = RuntimeError(f"arXiv SSL 验证失败（可能需要配置 ARXIV_HTTPS_PROXY）: {e}")
                logger.warning(f"arXiv SSL 错误 (attempt {attempt+1}/{self.max_retries+1}): {e}")
            except TimeoutError:
                last_error = RuntimeError(f"arXiv API 请求超时 ({self.timeout}秒，国内访问可能较慢)")
                logger.warning(f"arXiv 超时 (attempt {attempt+1}/{self.max_retries+1})")
            except ET.ParseError as e:
                logger.error(f"arXiv API XML 解析失败: {e}")
                raise RuntimeError("arXiv 返回数据解析失败") from e
            except Exception as e:
                last_error = RuntimeError(f"arXiv 搜索异常 ({type(e).__name__}): {e}")
                logger.warning(f"arXiv 未知错误 (attempt {attempt+1}/{self.max_retries+1}): {type(e).__name__}: {e}")

            if attempt < self.max_retries:
                time.sleep(5 * (2 ** attempt))

        raise last_error or RuntimeError("arXiv API 连接失败（已重试）")

    def _search_openalex(self, query: str, max_results: int) -> List[ArxivPaper]:
        """OpenAlex 降级检索，优先返回带 arXiv ID 的论文"""
        params = urllib.parse.urlencode({
            "search": query,
            "per_page": str(max(1, min(max_results, 25))),
            "sort": "relevance_score:desc",
        })
        url = f"{OPENALEX_API_BASE}?{params}"
        raw = self._fetch_text(url)
        payload = json.loads(raw)
        papers: List[ArxivPaper] = []

        for item in payload.get("results", []):
            title = (item.get("title") or "").strip()
            if not title:
                continue
            abstract = (item.get("abstract") or "") or self._reconstruct_openalex_abstract(
                item.get("abstract_inverted_index") or {}
            )
            authors = ", ".join(
                (a.get("author", {}) or {}).get("display_name", "")
                for a in (item.get("authorships") or [])
                if (a.get("author", {}) or {}).get("display_name")
            )
            published = item.get("publication_date") or ""
            published_at = None
            if published:
                try:
                    published_at = datetime.fromisoformat(published)
                except (ValueError, TypeError):
                    pass

            ids = item.get("ids") or {}
            arxiv_url = ids.get("arxiv") or ""
            arxiv_id = ""
            if arxiv_url:
                arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
                if arxiv_id.lower().startswith("arxiv:"):
                    arxiv_id = arxiv_id.split(":", 1)[-1]

            doi = (item.get("doi") or "").replace("https://doi.org/", "")
            papers.append(ArxivPaper(
                title=title,
                authors=authors,
                abstract=abstract[:2000] if abstract else "",
                published_at=published_at,
                categories="",
                external_id=arxiv_id,
                source_url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else (item.get("id") or ""),
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                source_type="arxiv" if arxiv_id else "openalex",
                doi=doi or None,
            ))

        return papers[:max_results]

    @staticmethod
    def _reconstruct_openalex_abstract(inverted_index: Dict[str, List[int]]) -> str:
        if not inverted_index:
            return ""
        max_pos = max(max(positions) for positions in inverted_index.values())
        words = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
        return " ".join(w for w in words if w)

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