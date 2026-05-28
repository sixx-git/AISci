"""
OpenAlex 文献搜索（免费开放 API，arXiv 不可用时的替代方案）

API: https://api.openalex.org/works?search={query}&per_page={n}
文档: https://docs.openalex.org/

返回标准化论文元数据，与 ArxivPaper.to_dict() 格式兼容。
"""
import urllib.request
import urllib.parse
import urllib.error
import ssl
import json
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

OPENALEX_API_BASE = "https://api.openalex.org/works"
OPENALEX_TIMEOUT = 15  # 秒


def _reconstruct_abstract(abstract_inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """OpenAlex 使用倒排索引存储摘要，需重建为自然文本"""
    if not abstract_inverted_index:
        return ""
    try:
        max_pos = max(max(positions) for positions in abstract_inverted_index.values() if positions)
        words = [""] * (max_pos + 1)
        for word, positions in abstract_inverted_index.items():
            for pos in positions:
                if 0 <= pos < len(words):
                    words[pos] = word
        return " ".join(words)
    except (ValueError, TypeError):
        return ""


class OpenAlexSource:
    """OpenAlex 文献数据源（arXiv 不可用时的替代方案）"""

    def __init__(self, timeout: int = OPENALEX_TIMEOUT, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries

    def search(
        self,
        query: str,
        max_results: int = 10,
        sort_by: str = "relevance",  # OpenAlex 支持: relevance, cited_by_count, publication_date
    ) -> List[Dict[str, Any]]:
        """
        搜索 OpenAlex 文献，返回与 ArxivPaper.to_dict() 兼容的 dict 列表

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            sort_by: 排序方式

        Returns:
            List[Dict]: 标准化论文元数据
        """
        if not query or not query.strip():
            raise ValueError("查询关键词不能为空")

        max_results = max(1, min(max_results, 100))

        # 添加过滤条件：优先期刊和会议论文
        params = {
            "search": query,
            "per_page": str(max_results),
            "sort": sort_by,
            "filter": "type:article|proceedings-article",  # 过滤非学术内容
        }
        url = f"{OPENALEX_API_BASE}?{urllib.parse.urlencode(params)}"

        logger.info(f"OpenAlex search: query='{query}', max_results={max_results}")

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(url)
                # OpenAlex 建议设置 User-Agent
                req.add_header("User-Agent", "AISci/1.0 (mailto:dev@example.com)")
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as response:
                    raw = response.read().decode("utf-8")

                data = json.loads(raw)
                results = data.get("results", [])
                papers = [self._convert_to_paper_dict(w) for w in results]
                logger.info(f"OpenAlex search returned {len(papers)} results")
                return papers

            except urllib.error.URLError as e:
                reason = str(e.reason) if e.reason else "Unknown Error"
                last_error = RuntimeError(f"OpenAlex API 连接失败: {reason}")
                logger.warning(f"OpenAlex 网络错误 (attempt {attempt+1}/{self.max_retries+1}): {reason}")
            except ssl.SSLError as e:
                last_error = RuntimeError(f"OpenAlex SSL 验证失败: {e}")
                logger.warning(f"OpenAlex SSL 错误 (attempt {attempt+1}/{self.max_retries+1}): {e}")
            except TimeoutError:
                last_error = RuntimeError(f"OpenAlex API 请求超时 ({self.timeout}秒)")
                logger.warning(f"OpenAlex 超时 (attempt {attempt+1}/{self.max_retries+1})")
            except json.JSONDecodeError as e:
                logger.error(f"OpenAlex JSON 解析失败: {e}")
                raise RuntimeError("OpenAlex 返回数据解析失败") from e
            except Exception as e:
                last_error = RuntimeError(f"OpenAlex 搜索异常 ({type(e).__name__}): {e}")
                logger.warning(f"OpenAlex 未知错误 (attempt {attempt+1}/{self.max_retries+1}): {type(e).__name__}: {e}")

            if attempt < self.max_retries:
                time.sleep(2 * (attempt + 1))

        raise last_error or RuntimeError("OpenAlex API 连接失败（已重试）")

    def _convert_to_paper_dict(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """将 OpenAlex work 转为与 ArxivPaper.to_dict() 兼容的格式"""
        # 提取作者
        authors_list = []
        for authorship in work.get("authorships", []):
            name = authorship.get("author", {}).get("display_name", "")
            if name:
                authors_list.append(name)
        authors = ", ".join(authors_list)

        # 提取 DOI
        doi = work.get("doi", "")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        # 提取年份/日期
        pub_year = work.get("publication_year")
        pub_date = work.get("publication_date", "")
        published_at = None
        if pub_date:
            try:
                published_at = datetime.fromisoformat(pub_date)
            except (ValueError, TypeError):
                if pub_year:
                    published_at = datetime(pub_year, 1, 1)

        elif pub_year:
            published_at = datetime(pub_year, 1, 1)

        # 期刊/会议信息
        primary_loc = work.get("primary_location", {}) or {}
        source_info = primary_loc.get("source", {}) or {}
        journal_ref = source_info.get("display_name", "")

        # 来源 URL
        source_url = primary_loc.get("landing_page_url", "")
        if not source_url and doi:
            source_url = f"https://doi.org/{doi}"

        # 外部分类 = OpenAlex concepts
        concepts = []
        for c in work.get("concepts", []):
            cname = c.get("display_name", "")
            if cname:
                concepts.append(cname)
        categories = ", ".join(concepts[:5])  # 最多5个领域

        # 摘要重建
        abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

        # OpenAlex ID 作为 external_id
        openalex_id = work.get("id", "")
        # 格式: https://openalex.org/Wxxxxxxxxx → 提取 Wxxxxxxxxx
        external_id = openalex_id.split("/")[-1] if openalex_id else ""

        return {
            "title": work.get("title") or work.get("display_name", ""),
            "authors": authors,
            "abstract": abstract,
            "published_at": published_at.isoformat() if published_at else None,
            "categories": categories,
            "external_id": external_id,
            "source_url": source_url,
            "pdf_url": "",  # OpenAlex 不直接提供 PDF
            "source_type": "openalex",  # 标记来源
            "doi": doi,
            "journal_ref": journal_ref,
            "comment": "",
        }