"""
元数据获取模块 — 通过 OpenAlex API 获取论文的引用数、期刊/会议、作者信息等。

OpenAlex API 免费使用，注册 API Key 后每天 $1 额度（约 50 次查询）。
无需 API Key 也可使用，但速率限制更严格（10 次/秒）。

API 文档: https://developers.openalex.org/
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"

# 默认 User-Agent（建议填入真实邮箱以获得更好的速率限制）
_DEFAULT_USER_AGENT = "mailto:rubric-tool@example.com"

# 请求超时
_TIMEOUT = 30

# 简单的内存缓存（避免短时间内重复请求同一 DOI）
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 小时


def _get(api_key: str = "") -> requests.Session:
    """创建带认证的 HTTP session。"""
    session = requests.Session()
    headers = {"User-Agent": _DEFAULT_USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    session.headers.update(headers)
    session.timeout = _TIMEOUT
    return session


def fetch_work_by_doi(doi: str, api_key: str = "") -> Optional[dict[str, Any]]:
    """通过 DOI 获取 OpenAlex Work 数据。

    Args:
        doi: DOI 字符串（可含或不含 https://doi.org/ 前缀）
        api_key: OpenAlex API Key（可选）

    Returns:
        OpenAlex Work 对象的摘要，或 None。
    """
    clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")

    # 处理 arXiv ID（arxiv:2106.09685v2 → OpenAlex DOI 格式）
    if clean_doi.startswith("arxiv:"):
        arxiv_id = clean_doi[len("arxiv:"):]
        # 去掉版本号（v2, v3 等），OpenAlex 使用不带版本的 ID
        arxiv_id_clean = re.sub(r'v\d+$', '', arxiv_id)
        # OpenAlex 中 arXiv 论文的 DOI 格式为 10.48550/arXiv.XXXX.XXXXX
        openalex_doi = f"10.48550/arXiv.{arxiv_id_clean}"
        clean_doi = openalex_doi
        logger.info("Converted arXiv ID to DOI: %s", clean_doi)

    # 检查缓存
    now = time.time()
    cache_key = f"work:{clean_doi}"
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    url = f"{OPENALEX_BASE}/works/doi:{clean_doi}"
    try:
        session = _get(api_key)
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code == 404:
            logger.warning("OpenAlex: DOI not found: %s", clean_doi)
            return None
        if resp.status_code != 200:
            logger.warning("OpenAlex API error %d for DOI %s", resp.status_code, clean_doi)
            return None

        data = resp.json()
        result = _summarize_work(data)
        _cache[cache_key] = (now, result)
        return result

    except requests.RequestException as e:
        logger.error("OpenAlex request failed: %s", e)
        return None


def fetch_work_by_title(title: str, api_key: str = "") -> Optional[dict[str, Any]]:
    """通过标题搜索获取 OpenAlex Work 数据（用于 DOI 提取失败时的降级方案）。

    只返回第一个匹配结果。
    """
    now = time.time()
    cache_key = f"title:{title[:100]}"
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    url = f"{OPENALEX_BASE}/works"
    params = {
        "search": title,
        "per_page": 1,
    }
    try:
        session = _get(api_key)
        resp = session.get(url, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None

        data = resp.json()
        results = data.get("results", [])
        if not results:
            logger.warning("OpenAlex: no results for title: %s", title[:80])
            return None

        result = _summarize_work(results[0])
        _cache[cache_key] = (now, result)
        return result

    except requests.RequestException as e:
        logger.error("OpenAlex title search failed: %s", e)
        return None


def fetch_author(author_id: str, api_key: str = "") -> Optional[dict[str, Any]]:
    """获取单个作者的摘要信息。"""
    clean_id = author_id.rstrip("/")
    cache_key = f"author:{clean_id}"
    now = time.time()
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    url = f"{OPENALEX_BASE}/authors/{clean_id}"
    try:
        session = _get(api_key)
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = {
            "display_name": data.get("display_name"),
            "works_count": data.get("works_count", 0),
            "cited_by_count": data.get("cited_by_count", 0),
            "last_known_institutions": [
                inst.get("display_name")
                for inst in data.get("last_known_institutions", [])
            ],
        }
        _cache[cache_key] = (now, result)
        return result
    except requests.RequestException:
        return None


def _summarize_work(raw: dict[str, Any]) -> dict[str, Any]:
    """将 OpenAlex Work 对象精简为摘要字典。"""
    host_venue = raw.get("host_venue") or {}
    authorships = raw.get("authorships") or []

    authors_summary = []
    institutions_set = set()
    author_ids = []

    for a in authorships[:10]:  # 最多取前 10 位作者
        author_info = a.get("author") or {}
        name = author_info.get("display_name", "Unknown")
        aid = author_info.get("id", "")
        author_ids.append(aid)

        insts = a.get("institutions") or []
        inst_names = [i.get("display_name", "") for i in insts if i.get("display_name")]
        for inst_name in inst_names:
            institutions_set.add(inst_name)

        authors_summary.append({
            "name": name,
            "institutions": inst_names,
        })

    concepts = []
    for c in (raw.get("concepts") or [])[:8]:
        concepts.append(c.get("display_name", ""))

    return {
        "openalex_id": raw.get("id", ""),
        "doi": raw.get("doi", ""),
        "title": raw.get("display_name", ""),
        "publication_year": raw.get("publication_year"),
        "publication_date": raw.get("publication_date", ""),
        "cited_by_count": raw.get("cited_by_count", 0),
        "open_access": (raw.get("open_access") or {}).get("is_oa", False),
        "host_venue": host_venue.get("display_name", ""),
        "host_venue_type": host_venue.get("type", ""),
        "host_venue_issn": host_venue.get("issn_l", ""),
        "authors": authors_summary,
        "author_ids": author_ids,
        "institutions": sorted(institutions_set),
        "concepts": concepts,
        "type": raw.get("type", ""),  # article, conference-paper, etc.
        "referenced_works_count": len(raw.get("referenced_works", [])),
    }
