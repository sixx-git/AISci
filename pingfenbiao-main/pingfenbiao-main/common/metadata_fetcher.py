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


_PREPRINT_TYPES = {"preprint", "posted-content"}
_PUBLISHED_TYPES = {
    "article",
    "journal-article",
    "conference-paper",
    "proceedings-article",
    "book-chapter",
    "dissertation",
    "review",
}


def _normalize_doi(doi: str) -> str:
    clean = (doi or "").replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    if clean.lower().startswith("arxiv:"):
        arxiv_id = clean[len("arxiv:"):]
        arxiv_id_clean = re.sub(r"v\d+$", "", arxiv_id, flags=re.I)
        clean = f"10.48550/arXiv.{arxiv_id_clean}"
        logger.info("Converted arXiv ID to DOI: %s", clean)
    return clean


def _is_arxiv_doi(doi: str) -> bool:
    d = (doi or "").lower()
    return "arxiv" in d or d.startswith("arxiv:")


def _normalize_title(title: str) -> str:
    text = re.sub(r"[^\w\s]", " ", (title or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _title_similar(a: str, b: str, min_overlap: float = 0.85) -> bool:
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / max(len(ta), len(tb)) >= min_overlap


def _work_rank(meta: dict[str, Any]) -> tuple:
    """越高越优先：正式发表 > 有 venue > 引用数。"""
    work_type = (meta.get("type") or "").lower()
    published = 1 if work_type in _PUBLISHED_TYPES else 0
    venue = 1 if (meta.get("host_venue") or "").strip() else 0
    cites = int(meta.get("cited_by_count") or 0)
    return (published, venue, cites)


def needs_published_upgrade(meta: Optional[dict[str, Any]]) -> bool:
    """预印本 / arXiv / 无 venue 低被引记录，需要尝试升级到正式版。"""
    if not meta:
        return False
    work_type = (meta.get("type") or "").lower()
    doi = meta.get("doi") or ""
    cites = int(meta.get("cited_by_count") or 0)
    venue = (meta.get("host_venue") or "").strip()
    if work_type in _PREPRINT_TYPES or _is_arxiv_doi(doi):
        return True
    if not venue and cites <= 3 and work_type not in _PUBLISHED_TYPES:
        return True
    return False


def _fetch_work_by_doi_raw(doi: str, api_key: str = "") -> Optional[dict[str, Any]]:
    """按 DOI 拉取 OpenAlex 摘要（不做正式版升级）。"""
    clean_doi = _normalize_doi(doi)
    if not clean_doi:
        return None

    now = time.time()
    cache_key = f"work:{clean_doi.lower()}"
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

        result = _summarize_work(resp.json())
        _cache[cache_key] = (now, result)
        return result
    except requests.RequestException as e:
        logger.error("OpenAlex request failed: %s", e)
        return None


def search_works_by_title(
    title: str,
    per_page: int = 8,
    api_key: str = "",
) -> list[dict[str, Any]]:
    """按标题搜索多条 OpenAlex 候选。"""
    if not (title or "").strip():
        return []

    url = f"{OPENALEX_BASE}/works"
    params = {"search": title.strip(), "per_page": max(1, min(per_page, 25))}
    try:
        session = _get(api_key)
        resp = session.get(url, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("OpenAlex title search error %d", resp.status_code)
            return []
        results = resp.json().get("results") or []
        return [_summarize_work(item) for item in results if isinstance(item, dict)]
    except requests.RequestException as e:
        logger.error("OpenAlex title search failed: %s", e)
        return []


def _fetch_crossref_best_doi(title: str) -> Optional[str]:
    """用 Crossref 标题检索，优先返回非 arXiv 的正式 DOI。"""
    if not (title or "").strip():
        return None
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": _DEFAULT_USER_AGENT})
        resp = session.get(
            "https://api.crossref.org/works",
            params={"query.title": title.strip(), "rows": 5},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        items = ((resp.json() or {}).get("message") or {}).get("items") or []
        best_doi = None
        best_rank = (-1, -1)
        for item in items:
            if not isinstance(item, dict):
                continue
            item_title = " ".join(item.get("title") or [])
            if not _title_similar(title, item_title):
                continue
            doi = (item.get("DOI") or "").strip()
            if not doi:
                continue
            published = 0 if _is_arxiv_doi(doi) else 1
            cites = int(item.get("is-referenced-by-count") or 0)
            rank = (published, cites)
            if rank > best_rank:
                best_rank = rank
                best_doi = doi
        return best_doi
    except requests.RequestException as e:
        logger.warning("Crossref title lookup failed: %s", e)
        return None


def upgrade_to_published_version(
    meta: dict[str, Any],
    title: str = "",
    api_key: str = "",
) -> dict[str, Any]:
    """若当前记录是预印本/低被引 arXiv，尝试升级到正式发表版本。"""
    if not meta or not needs_published_upgrade(meta):
        return meta

    search_title = (title or meta.get("title") or "").strip()
    if not search_title:
        return meta

    best = meta
    for cand in search_works_by_title(search_title, per_page=8, api_key=api_key):
        if not _title_similar(search_title, cand.get("title") or ""):
            continue
        if _work_rank(cand) > _work_rank(best):
            best = cand

    if needs_published_upgrade(best):
        cr_doi = _fetch_crossref_best_doi(search_title)
        if cr_doi and not _is_arxiv_doi(cr_doi):
            published = _fetch_work_by_doi_raw(cr_doi, api_key=api_key)
            if published and _title_similar(search_title, published.get("title") or ""):
                if _work_rank(published) > _work_rank(best):
                    best = published

    if best is meta or _work_rank(best) <= _work_rank(meta):
        return meta

    upgraded = dict(best)
    upgraded["_upgraded_from"] = {
        "openalex_id": meta.get("openalex_id"),
        "doi": meta.get("doi"),
        "type": meta.get("type"),
        "cited_by_count": meta.get("cited_by_count", 0),
        "host_venue": meta.get("host_venue", ""),
    }
    logger.info(
        "Upgraded metadata %s (cites=%s, type=%s) -> %s (cites=%s, type=%s, venue=%s)",
        meta.get("doi"),
        meta.get("cited_by_count"),
        meta.get("type"),
        upgraded.get("doi"),
        upgraded.get("cited_by_count"),
        upgraded.get("type"),
        upgraded.get("host_venue"),
    )
    return upgraded


def fetch_work_by_doi(
    doi: str,
    api_key: str = "",
    *,
    resolve_published: bool = True,
) -> Optional[dict[str, Any]]:
    """通过 DOI 获取 OpenAlex Work 数据。

    Args:
        doi: DOI 字符串（可含或不含 https://doi.org/ 前缀）
        api_key: OpenAlex API Key（可选）
        resolve_published: 预印本时是否尝试升级到正式发表版本

    Returns:
        OpenAlex Work 对象的摘要，或 None。
    """
    result = _fetch_work_by_doi_raw(doi, api_key=api_key)
    if result and resolve_published:
        result = upgrade_to_published_version(
            result, title=result.get("title") or "", api_key=api_key
        )
    return result


def fetch_work_by_title(title: str, api_key: str = "") -> Optional[dict[str, Any]]:
    """通过标题搜索获取 OpenAlex Work 数据（用于 DOI 提取失败时的降级方案）。

    在多条候选中优先选择正式发表、高被引版本。
    """
    now = time.time()
    cache_key = f"title-best:{title[:100]}"
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    candidates = search_works_by_title(title, per_page=8, api_key=api_key)
    if not candidates:
        logger.warning("OpenAlex: no results for title: %s", title[:80])
        return None

    best = candidates[0]
    for cand in candidates[1:]:
        if _title_similar(title, cand.get("title") or "") and _work_rank(cand) > _work_rank(best):
            best = cand
        elif not _title_similar(title, best.get("title") or "") and _title_similar(
            title, cand.get("title") or ""
        ):
            best = cand

    best = upgrade_to_published_version(best, title=title, api_key=api_key)
    _cache[cache_key] = (now, best)
    return best


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _display_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("display_name") or "")
    if isinstance(value, str):
        return value
    return ""


def _summarize_work(raw: dict[str, Any]) -> dict[str, Any]:
    """将 OpenAlex Work 对象精简为摘要字典。"""
    if not isinstance(raw, dict):
        return {
            "openalex_id": "",
            "doi": "",
            "title": "",
            "publication_year": None,
            "publication_date": "",
            "cited_by_count": 0,
            "open_access": False,
            "host_venue": "",
            "host_venue_type": "",
            "host_venue_issn": "",
            "authors": [],
            "author_ids": [],
            "institutions": [],
            "concepts": [],
            "type": "",
            "referenced_works_count": 0,
        }

    host_venue = _as_mapping(raw.get("host_venue"))
    primary_location = _as_mapping(raw.get("primary_location"))
    primary_source = _as_mapping(primary_location.get("source"))
    # OpenAlex 新 API 常用 primary_location.source，host_venue 可能为空
    venue_name = (
        host_venue.get("display_name")
        or primary_source.get("display_name")
        or _display_name(raw.get("host_venue"))
        or ""
    )
    venue_type = host_venue.get("type") or primary_source.get("type") or ""
    venue_issn = host_venue.get("issn_l") or primary_source.get("issn_l") or ""

    authorships = raw.get("authorships") or []
    if not isinstance(authorships, list):
        authorships = []

    authors_summary = []
    institutions_set = set()
    author_ids = []

    for a in authorships[:10]:  # 最多取前 10 位作者
        if not isinstance(a, dict):
            if isinstance(a, str) and a.strip():
                authors_summary.append({"name": a.strip(), "institutions": []})
            continue
        author_info = _as_mapping(a.get("author"))
        name = author_info.get("display_name") or _display_name(a.get("author")) or "Unknown"
        aid = author_info.get("id", "")
        author_ids.append(aid)

        insts = a.get("institutions") or []
        if not isinstance(insts, list):
            insts = []
        inst_names = []
        for i in insts:
            name_i = _display_name(i)
            if name_i:
                inst_names.append(name_i)
                institutions_set.add(name_i)

        authors_summary.append({
            "name": name,
            "institutions": inst_names,
        })

    concepts = _extract_subject_labels(raw)

    open_access = _as_mapping(raw.get("open_access"))
    referenced = raw.get("referenced_works") or []
    if not isinstance(referenced, list):
        referenced = []

    return {
        "openalex_id": raw.get("id", ""),
        "doi": raw.get("doi", ""),
        "title": raw.get("display_name", ""),
        "publication_year": raw.get("publication_year"),
        "publication_date": raw.get("publication_date", ""),
        "cited_by_count": raw.get("cited_by_count", 0),
        "open_access": bool(open_access.get("is_oa", False)),
        "host_venue": venue_name,
        "host_venue_type": venue_type,
        "host_venue_issn": venue_issn,
        "authors": authors_summary,
        "author_ids": author_ids,
        "institutions": sorted(institutions_set),
        "concepts": concepts,
        "type": raw.get("type", ""),  # article, conference-paper, etc.
        "referenced_works_count": len(referenced),
    }


# OpenAlex 低分 concept 常含跨学科噪声（如 Chromatography/Psychology），需按分数过滤。
_CONCEPT_MIN_SCORE = 0.40
_CONCEPT_SOFT_MIN_SCORE = 0.30
_CONCEPT_SOFT_ALLOW = {
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "computer science",
    "federated learning",
}
_MAX_SUBJECT_LABELS = 6


def _extract_subject_labels(raw: dict[str, Any]) -> list[str]:
    """从 OpenAlex concepts/topics 提取主题标签，过滤低分噪声。"""
    scored: list[tuple[float, str]] = []

    for c in raw.get("concepts") or []:
        if not isinstance(c, dict):
            continue
        name = _display_name(c).strip()
        if not name:
            continue
        try:
            score = float(c.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        key = name.lower()
        if score >= _CONCEPT_MIN_SCORE or (
            score >= _CONCEPT_SOFT_MIN_SCORE and key in _CONCEPT_SOFT_ALLOW
        ):
            scored.append((score, name))

    # topics 相关性不稳定，只保留最高分的 1 条，避免噪声主题混入
    best_topic: tuple[float, str] | None = None
    for t in raw.get("topics") or []:
        if not isinstance(t, dict):
            continue
        name = _display_name(t).strip()
        if not name:
            continue
        try:
            score = float(t.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if best_topic is None or score > best_topic[0]:
            best_topic = (score, name)
    if best_topic is not None and best_topic[0] > 0:
        scored.append(best_topic)

    scored.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    labels: list[str] = []
    for _score, name in scored:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(name)
        if len(labels) >= _MAX_SUBJECT_LABELS:
            break

    # 兜底：若过滤后为空，退回最高分的 3 个 concept（仍优于盲目取前 8 个）
    if not labels:
        fallback: list[tuple[float, str]] = []
        for c in raw.get("concepts") or []:
            if not isinstance(c, dict):
                continue
            name = _display_name(c).strip()
            if not name:
                continue
            try:
                score = float(c.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            fallback.append((score, name))
        fallback.sort(key=lambda x: x[0], reverse=True)
        for _score, name in fallback[:3]:
            labels.append(name)
    return labels

