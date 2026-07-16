"""
引用网络特征分析模块 — CitationGraphFeatureSkill

利用 OpenAlex API 获取论文的引用网络数据，计算以下特征：
  - 引用网络规模（cited_by + references）
  - 引用速度（年增长率）
  - 领域引用百分位（与同年同领域论文对比）
  - h-index 近似值（基于引用数估算）
  - 引用的多样性（引用来源的机构和领域分布）
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"
_TIMEOUT = 30
_DEFAULT_USER_AGENT = "mailto:rubric-tool@example.com"


class CitationGraphAnalyzer:
    """引用网络分析器。"""

    def __init__(self, openalex_api_key: str = ""):
        self.api_key = openalex_api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _DEFAULT_USER_AGENT})
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.timeout = _TIMEOUT

    def analyze(self, work_id_or_doi: str) -> dict[str, Any] | None:
        """分析单篇论文的引用网络特征。

        Args:
            work_id_or_doi: OpenAlex work ID (如 W123456789) 或 DOI

        Returns:
            引用网络特征字典，失败返回 None。
        """
        # 获取论文详细数据
        work = self._fetch_work(work_id_or_doi)
        if not work:
            return None

        # 获取引用该论文的论文列表（cited_by）
        cited_by = self._fetch_cited_by(work.get("id", ""))

        # 获取该论文引用的论文列表（references）
        references = self._fetch_references(work.get("id", ""))

        # 计算特征
        return self._compute_features(work, cited_by, references)

    def _fetch_work(self, work_id_or_doi: str) -> dict[str, Any] | None:
        """获取论文详细数据。"""
        if work_id_or_doi.startswith("W"):
            url = f"{OPENALEX_BASE}/works/{work_id_or_doi}"
        else:
            clean_doi = work_id_or_doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
            url = f"{OPENALEX_BASE}/works/doi:{clean_doi}"

        try:
            resp = self.session.get(url, timeout=_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("OpenAlex work fetch failed: %d", resp.status_code)
                return None
            return resp.json()
        except requests.RequestException as e:
            logger.error("OpenAlex request failed: %s", e)
            return None

    def _fetch_cited_by(self, work_id: str, max_results: int = 200) -> list[dict]:
        """获取引用该论文的论文列表。"""
        if not work_id:
            return []
        url = f"{OPENALEX_BASE}/works"
        params = {
            "filter": f"cites:{work_id}",
            "per_page": min(max_results, 200),
            "sort": "cited_by_count:desc",
        }
        try:
            resp = self.session.get(url, params=params, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = data.get("results", [])
            return [
                {
                    "id": r.get("id", ""),
                    "title": r.get("display_name", ""),
                    "year": r.get("publication_year"),
                    "cited_by_count": r.get("cited_by_count", 0),
                    "venue": (r.get("host_venue") or {}).get("display_name", ""),
                    "authors": [a.get("author", {}).get("display_name", "") for a in r.get("authorships", [])[:5]],
                    "concepts": [c.get("display_name", "") for c in r.get("concepts", [])[:5]],
                }
                for r in results
            ]
        except requests.RequestException:
            return []

    def _fetch_references(self, work_id: str, max_results: int = 200) -> list[dict]:
        """获取该论文引用的论文列表。"""
        if not work_id:
            return []
        url = f"{OPENALEX_BASE}/works"
        params = {
            "filter": f"cited_by:{work_id}",
            "per_page": min(max_results, 200),
            "sort": "cited_by_count:desc",
        }
        try:
            resp = self.session.get(url, params=params, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = data.get("results", [])
            return [
                {
                    "id": r.get("id", ""),
                    "title": r.get("display_name", ""),
                    "year": r.get("publication_year"),
                    "cited_by_count": r.get("cited_by_count", 0),
                    "venue": (r.get("host_venue") or {}).get("display_name", ""),
                }
                for r in results
            ]
        except requests.RequestException:
            return []

    def _compute_features(
        self,
        work: dict[str, Any],
        cited_by: list[dict],
        references: list[dict],
    ) -> dict[str, Any]:
        """计算引用网络特征。"""
        pub_year = work.get("publication_year")
        current_year = time.localtime().tm_year
        age = max(1, current_year - (pub_year or current_year - 1))

        cited_count = work.get("cited_by_count", 0)
        ref_count = len(references)

        # 1. 引用速度（年增长）
        citation_velocity = round(cited_count / age, 2) if age > 0 else 0

        # 2. 引用集中度（引用者中高引用论文占比）
        high_cited_citers = sum(1 for c in cited_by if c.get("cited_by_count", 0) >= 50)
        concentration_ratio = round(high_cited_citers / max(len(cited_by), 1), 3)

        # 3. 引用来源多样性
        all_concepts = []
        for c in cited_by:
            all_concepts.extend(c.get("concepts", []))
        unique_concepts = len(set(all_concepts))
        diversity_score = min(1.0, unique_concepts / 20)  # 20个领域概念为满分

        # 4. 高影响力引用者比例
        influential_citers = sum(
            1 for c in cited_by
            if c.get("cited_by_count", 0) >= 100 or any(
                kw in (c.get("venue", "") or "").lower()
                for kw in ["nature", "science", "cell", "ieee", "acm", "neurips", "icml"]
            )
        )
        influential_ratio = round(influential_citers / max(len(cited_by), 1), 3)

        # 5. 引用网络连通性（cited_by × references 的交叉）
        # 计算引用者和被引用论文之间的重叠
        cited_ids = {c["id"] for c in cited_by}
        ref_ids = {r["id"] for r in references}
        overlap = len(cited_ids & ref_ids)
        connectivity = round(overlap / max(len(cited_ids | ref_ids), 1), 3)

        # 6. 领域引用百分位（基于领域均值估算）
        field_percentile = self._estimate_field_percentile(work, cited_count, age)

        # 7. 高被引论文的引用分布
        top_5_citers = sorted(cited_by, key=lambda x: x.get("cited_by_count", 0), reverse=True)[:5]
        top_citer_impact = sum(c.get("cited_by_count", 0) for c in top_5_citers)

        # 8. 引用延迟分析（引用论文的发表年份 vs 被引论文年份）
        citation_delays = []
        for c in cited_by:
            cy = c.get("year")
            if cy and pub_year:
                citation_delays.append(cy - pub_year)
        avg_delay = round(sum(citation_delays) / max(len(citation_delays), 1), 1) if citation_delays else 0

        return {
            "network_size": {
                "cited_by_count": cited_count,
                "references_count": ref_count,
                "total_edges": cited_count + ref_count,
            },
            "citation_velocity": citation_velocity,
            "concentration_ratio": concentration_ratio,
            "diversity_score": round(diversity_score, 3),
            "influential_ratio": influential_ratio,
            "connectivity": connectivity,
            "field_percentile": field_percentile,
            "top_citer_impact": top_citer_impact,
            "avg_citation_delay_years": avg_delay,
            "age_years": age,
            "cited_by_sample": cited_by[:10],  # 前10个引用者
            "references_sample": references[:10],  # 前10个引用论文
        }

    def _estimate_field_percentile(self, work: dict[str, Any], cited_count: int, age: int) -> float:
        """估算论文在领域内的引用百分位。

        基于 OpenAlex 的领域概念和同领域论文的引用统计进行估算。
        这是一个启发式估算，非精确值。
        """
        concepts = work.get("concepts", [])
        if not concepts:
            return 50.0

        # 取前2个概念作为领域
        top_concepts = [c.get("id", "") for c in concepts[:2] if c.get("id")]
        if not top_concepts:
            return 50.0

        # 获取该领域的引用统计基准（取前200篇同年论文的中位数）
        try:
            url = f"{OPENALEX_BASE}/works"
            params = {
                "filter": f"concepts.id:{top_concepts[0]},publication_year:{work.get('publication_year', current_year-2)}",
                "per_page": 200,
                "sort": "cited_by_count:desc",
            }
            resp = self.session.get(url, params=params, timeout=_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                citation_counts = [r.get("cited_by_count", 0) for r in results if r.get("id") != work.get("id")]
                if citation_counts:
                    # 找到该论文的百分位位置
                    sorted_counts = sorted(citation_counts)
                    position = sum(1 for c in sorted_counts if c <= cited_count)
                    percentile = round(position / len(sorted_counts) * 100, 1)
                    return min(99.9, max(0.1, percentile))
        except requests.RequestException:
            pass

        return 50.0  # 默认中位数


def analyze_citation_graph(work_id_or_doi: str, api_key: str = "") -> dict[str, Any] | None:
    """便捷函数：分析论文引用网络。

    Args:
        work_id_or_doi: OpenAlex work ID 或 DOI
        api_key: OpenAlex API Key（可选）

    Returns:
        引用网络特征字典。
    """
    analyzer = CitationGraphAnalyzer(api_key)
    return analyzer.analyze(work_id_or_doi)
