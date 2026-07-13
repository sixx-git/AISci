"""
多源论文搜索 Skill
参考能力：Hermes research/arxiv、AI Scientist v3 search-papers、
Semantic Scholar Skills、OpenAlex
——基于 research_question / keywords 搜索 arXiv、Semantic Scholar、
OpenAlex、CrossRef，返回统一 paper metadata。
"""
import asyncio
import logging
import json
import hashlib
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Set, Tuple

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

PAPER_SOURCES = ["arxiv", "semantic_scholar", "openalex", "crossref"]
REQUEST_TIMEOUT = 15
SOURCE_INTERVAL_SEC = 2.0
ARXIV_MIN_INTERVAL_SEC = 4.0
HTTP_RETRY_MAX = 4
HTTP_RETRY_BASE_DELAY_SEC = 5.0

_arxiv_rate_lock = threading.Lock()
_arxiv_last_request_at = 0.0

API_CONFIG = {
    "semantic_scholar": {
        "search_url": "https://api.semanticscholar.org/graph/v1/paper/search",
        "fields": "title,authors,year,abstract,externalIds,url,venue,citationCount,publicationTypes",
    },
    "openalex": {
        "search_url": "https://api.openalex.org/works",
        "per_page": 25,
    },
    "crossref": {
        "search_url": "https://api.crossref.org/works",
        "rows": 25,
    },
    "arxiv": {
        "search_url": "https://export.arxiv.org/api/query",
        "max_results": 30,
    },
}


class SearchPapersSkill(BaseSkill):
    """多源论文搜索 Skill

    输入:
      - research_question: str        研究问题
      - keywords: List[str]           额外关键词
      - max_results: int = 30         最大返回数（跨所有源）
      - sources: List[str]            指定搜索源，默认全部

    输出 (SkillResult.data):
      - papers: List[dict]            统一格式论文元数据
      - total: int                    实际返回数量
      - sources_searched: List[str]   实际搜索的源
      - dedup_count: int              去重数量
      - warnings: List[str]           各源降级/失败警告
    """

    name = "SearchPapers"
    description = "根据研究问题和关键词从 arXiv、Semantic Scholar、OpenAlex、CrossRef 检索论文"
    source_reference = (
        "Hermes (arxiv:2501.11111) — 学术检索能力参考; "
        "AI Scientist v3 — search-papers; "
        "Semantic Scholar API; OpenAlex API; CrossRef API"
    )

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        research_question = input_data.get("research_question", "")
        keywords: List[str] = input_data.get("keywords", [])
        max_results = min(input_data.get("max_results", 30), 60)
        sources: List[str] = input_data.get("sources", list(PAPER_SOURCES))

        if not isinstance(keywords, list):
            keywords = []

        sources = [s.lower() for s in sources if s.lower() in PAPER_SOURCES]
        if not sources:
            sources = ["arxiv", "semantic_scholar"]

        query_terms = [research_question] if research_question else []
        query_terms.extend(k for k in keywords if isinstance(k, str) and k.strip())
        if not query_terms:
            result.add_error("搜索关键词为空")
            return result

        from app.services.literature_search_utils import normalize_api_search_query

        search_query = normalize_api_search_query(" ".join(query_terms[:5]))
        if not search_query:
            search_query = " ".join(query_terms[:5])[:240]

        all_papers: List[dict] = []
        source_status: Dict[str, dict] = {}
        source_warnings: List[str] = []

        for source_idx, source_name in enumerate(sources):
            if source_idx > 0:
                await asyncio.sleep(SOURCE_INTERVAL_SEC)
            try:
                source_papers = await self._search_source(source_name, search_query, max_results)
                for p in source_papers:
                    p["_source"] = source_name
                all_papers.extend(source_papers)
                source_status[source_name] = {"success": True, "count": len(source_papers)}
                logger.info(f"{source_name}: {len(source_papers)} papers")
            except Exception as e:
                warn_msg = f"{source_name} 搜索失败: {str(e)[:120]}"
                source_warnings.append(warn_msg)
                source_status[source_name] = {"success": False, "count": 0, "error": str(e)[:200]}
                logger.warning(warn_msg)
                result.add_warning(warn_msg)

        deduped, dedup_count = self._deduplicate_papers(all_papers)
        deduped = deduped[:max_results]

        for paper in deduped:
            paper.pop("_source", None)

        result.data = {
            "papers": deduped,
            "total": len(deduped),
            "sources_searched": sources,
            "dedup_count": dedup_count,
            "source_status": source_status,
            "warnings": source_warnings,
        }
        result.metadata["sources_with_errors"] = len(source_warnings)
        return result

    async def _search_source(self, source: str, query: str, max_results: int) -> List[dict]:
        if source == "arxiv":
            return await self._search_arxiv(query, max_results)
        elif source == "semantic_scholar":
            return await self._search_semantic_scholar(query, max_results)
        elif source == "openalex":
            return await self._search_openalex(query, max_results)
        elif source == "crossref":
            return await self._search_crossref(query, max_results)
        return []

    async def _search_arxiv(self, query: str, max_results: int) -> List[dict]:
        encoded_query = urllib.parse.quote(query)
        url = (
            f"{API_CONFIG['arxiv']['search_url']}"
            f"?search_query=all:{encoded_query}"
            f"&start=0&max_results={min(max_results, API_CONFIG['arxiv']['max_results'])}"
        )
        xml_data = await asyncio.to_thread(self._fetch_arxiv_xml_with_retry, url)

        root = ET.fromstring(xml_data)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        papers = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
            summary_el = entry.find("atom:summary", ns)
            abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())
            published_el = entry.find("atom:published", ns)
            year = None
            if published_el is not None and published_el.text:
                try:
                    year = int(published_el.text[:4])
                except (ValueError, IndexError):
                    pass
            url_el = entry.find("atom:id", ns)
            source_url = (url_el.text or "").strip() if url_el is not None else ""
            arxiv_id = source_url.split("/abs/")[-1] if "/abs/" in source_url else ""
            if "v" in arxiv_id:
                arxiv_id = arxiv_id.rsplit("v", 1)[0]

            papers.append({
                "title": title,
                "authors": authors,
                "year": year,
                "abstract": abstract,
                "source": "arxiv",
                "source_url": source_url,
                "doi": "",
                "arxiv_id": arxiv_id,
                "citation_count": 0,
                "venue": "",
                "pdf_url": source_url.replace("/abs/", "/pdf/") if arxiv_id else "",
                "external_id": arxiv_id,
                "metadata": {"source_api": "arxiv", "raw_id": arxiv_id},
            })
        return papers

    async def _search_semantic_scholar(self, query: str, max_results: int) -> List[dict]:
        params = {
            "query": query,
            "limit": min(max_results, 30),
            "fields": API_CONFIG["semantic_scholar"]["fields"],
            "offset": 0,
        }
        url = f"{API_CONFIG['semantic_scholar']['search_url']}?{urllib.parse.urlencode(params)}"
        data = await self._http_get_json(url, source_name="semantic_scholar")
        papers = []
        for item in data.get("data", []):
            authors_list = []
            for a in item.get("authors", []):
                authors_list.append(a.get("name", ""))
            ext_ids = item.get("externalIds", {})
            papers.append({
                "title": item.get("title", "") or "",
                "authors": authors_list,
                "year": item.get("year"),
                "abstract": item.get("abstract", "") or "",
                "source": "semantic_scholar",
                "source_url": item.get("url", "") or "",
                "doi": ext_ids.get("DOI", "") or "",
                "arxiv_id": ext_ids.get("ArXiv", "") or "",
                "citation_count": item.get("citationCount", 0) or 0,
                "venue": item.get("venue", "") or "",
                "pdf_url": "",
                "external_id": ext_ids.get("ArXiv", "") or ext_ids.get("DOI", "") or str(item.get("paperId", "")),
                "metadata": {"source_api": "semantic_scholar", "paperId": item.get("paperId", ""), "external_ids": ext_ids},
            })
        return papers

    async def _search_openalex(self, query: str, max_results: int) -> List[dict]:
        params = {
            "search": query,
            "per_page": min(max_results, API_CONFIG["openalex"]["per_page"]),
            "sort": "cited_by_count:desc",
            "filter": "has_abstract:true",
        }
        url = f"{API_CONFIG['openalex']['search_url']}?{urllib.parse.urlencode(params)}"
        data = await self._http_get_json(url, source_name="openalex")
        papers = []
        for item in data.get("results", []):
            authors_list = []
            for a in item.get("authorships", []):
                author_obj = a.get("author", {})
                authors_list.append(author_obj.get("display_name", ""))
            primary_loc = item.get("primary_location", {}) or {}
            source_info = primary_loc.get("source", {}) or {}
            openalex_id = item.get("id", "") or ""
            papers.append({
                "title": item.get("title", "") or "",
                "authors": authors_list,
                "year": item.get("publication_year"),
                "abstract": "",
                "source": "openalex",
                "source_url": item.get("doi", "") and f"https://doi.org/{item['doi']}" or "",
                "doi": item.get("doi", "") or "",
                "arxiv_id": "",
                "citation_count": item.get("cited_by_count", 0) or 0,
                "venue": source_info.get("display_name", "") or "",
                "pdf_url": primary_loc.get("pdf_url", "") or "",
                "external_id": openalex_id.split("/")[-1] if openalex_id else "",
                "metadata": {"source_api": "openalex", "openalex_id": openalex_id, "type": item.get("type", "")},
            })
            if item.get("abstract_inverted_index"):
                abstract = self._reconstruct_openalex_abstract(item["abstract_inverted_index"])
                papers[-1]["abstract"] = abstract
        return papers

    @staticmethod
    def _reconstruct_openalex_abstract(inverted_index: dict) -> str:
        if not inverted_index:
            return ""
        word_positions: List[Tuple[int, str]] = []
        for word, positions in inverted_index.items():
            if not isinstance(positions, list):
                continue
            for pos in positions:
                if isinstance(pos, int):
                    word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)

    async def _search_crossref(self, query: str, max_results: int) -> List[dict]:
        params = {
            "query.bibliographic": query,
            "rows": min(max_results, API_CONFIG["crossref"]["rows"]),
            "sort": "relevance",
        }
        url = f"{API_CONFIG['crossref']['search_url']}?{urllib.parse.urlencode(params)}"
        data = await self._http_get_json(url, source_name="crossref")
        papers = []
        items = data.get("message", {}).get("items", [])
        for item in items:
            authors_list = []
            for a in item.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                full = f"{given} {family}".strip()
                if full:
                    authors_list.append(full)
            published = item.get("published-print", {}) or item.get("created", {})
            date_parts = published.get("date-parts", [[None]])
            year = date_parts[0][0] if date_parts and date_parts[0] else None
            papers.append({
                "title": (item.get("title", [""]) or [""])[0],
                "authors": authors_list,
                "year": int(year) if year else None,
                "abstract": (item.get("abstract", "") or ""),
                "source": "crossref",
                "source_url": item.get("URL", "") or (f"https://doi.org/{item['DOI']}" if item.get("DOI") else ""),
                "doi": item.get("DOI", "") or "",
                "arxiv_id": "",
                "citation_count": item.get("is-referenced-by-count", 0) or 0,
                "venue": (item.get("container-title", [""]) or [""])[0],
                "pdf_url": "",
                "external_id": item.get("DOI", "") or "",
                "metadata": {"source_api": "crossref", "publisher": item.get("publisher", ""), "type": item.get("type", "")},
            })
        return papers

    @classmethod
    def _wait_arxiv_slot(cls) -> None:
        global _arxiv_last_request_at
        with _arxiv_rate_lock:
            now = time.monotonic()
            wait = ARXIV_MIN_INTERVAL_SEC - (now - _arxiv_last_request_at)
            if wait > 0:
                time.sleep(wait)
            _arxiv_last_request_at = time.monotonic()

    @classmethod
    def _fetch_arxiv_xml_with_retry(cls, url: str) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(HTTP_RETRY_MAX):
            cls._wait_arxiv_slot()
            req = urllib.request.Request(url, headers={"User-Agent": "AISci/1.0 (mailto:dev@aiscilab.org)"})
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    return resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300]
                last_error = RuntimeError(f"arXiv HTTP {e.code}: {body}")
                if e.code == 429 and attempt < HTTP_RETRY_MAX - 1:
                    delay = HTTP_RETRY_BASE_DELAY_SEC * (2 ** attempt)
                    logger.warning("arXiv 429，%ss 后重试 (%d/%d)", delay, attempt + 1, HTTP_RETRY_MAX)
                    time.sleep(delay)
                    continue
                raise last_error from e
            except urllib.error.URLError as e:
                last_error = RuntimeError(f"arXiv API 不可达: {e}")
                if attempt < HTTP_RETRY_MAX - 1:
                    time.sleep(HTTP_RETRY_BASE_DELAY_SEC * (attempt + 1))
                    continue
                raise last_error from e
        raise last_error or RuntimeError("arXiv API 请求失败")

    @classmethod
    def _http_get_json_sync(cls, url: str, *, source_name: str = "api") -> dict:
        last_error: Optional[Exception] = None
        for attempt in range(HTTP_RETRY_MAX):
            if source_name == "arxiv":
                cls._wait_arxiv_slot()
            req = urllib.request.Request(url, headers={"User-Agent": "AISci/1.0 (mailto:dev@aiscilab.org)"})
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:300]
                last_error = RuntimeError(f"HTTP {e.code}: {body}")
                if e.code in (429, 503) and attempt < HTTP_RETRY_MAX - 1:
                    delay = HTTP_RETRY_BASE_DELAY_SEC * (2 ** attempt)
                    logger.warning("%s HTTP %d，%ss 后重试 (%d/%d)", source_name, e.code, delay, attempt + 1, HTTP_RETRY_MAX)
                    time.sleep(delay)
                    continue
                raise last_error from e
            except urllib.error.URLError as e:
                last_error = RuntimeError(f"网络不可达: {e}")
                if attempt < HTTP_RETRY_MAX - 1:
                    time.sleep(HTTP_RETRY_BASE_DELAY_SEC * (attempt + 1))
                    continue
                raise last_error from e
        raise last_error or RuntimeError(f"{source_name} API 请求失败")

    @classmethod
    async def _http_get_json(cls, url: str, *, source_name: str = "api") -> dict:
        return await asyncio.to_thread(cls._http_get_json_sync, url, source_name=source_name)

    @staticmethod
    def _generate_paper_key(paper: dict) -> Optional[str]:
        doi = (paper.get("doi") or "").strip().lower()
        if doi and len(doi) >= 5:
            return f"doi:{doi}"
        arxiv = (paper.get("arxiv_id") or "").strip().lower()
        if arxiv and len(arxiv) >= 5:
            return f"arxiv:{arxiv}"
        title = (paper.get("title") or "").strip().lower()
        if title:
            normalized = " ".join(title.split()).lower()
            normalized = "".join(c for c in normalized if c.isalnum() or c.isspace())
            if len(normalized) >= 20:
                return f"title:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"
        return None

    def _deduplicate_papers(self, papers: List[dict]) -> Tuple[List[dict], int]:
        seen_keys: Set[str] = set()
        deduped: List[dict] = []
        for paper in papers:
            key = self._generate_paper_key(paper)
            if key is None:
                deduped.append(paper)
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(paper)
        dedup_count = len(papers) - len(deduped)
        return deduped, dedup_count