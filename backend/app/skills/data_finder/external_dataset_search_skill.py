"""外部数据集检索 Skill"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from app.core.research_field import (
    build_external_search_query,
    build_research_context,
    filter_relevant_external_candidates,
    should_search_biomedical_sources,
)
from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 12


class ExternalDatasetSearchSkill(BaseSkill):
    name = "ExternalDatasetSearch"
    description = "按研究领域检索开放数据候选（生医才查 GEO；全领域经相关性过滤）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = input_data.get("research_question", "")
        dataset_keywords = input_data.get("dataset_keywords", []) or []
        research_domain = input_data.get("research_domain", "") or ""
        data_spec = input_data.get("data_spec") if isinstance(input_data.get("data_spec"), dict) else {}

        field_context = build_research_context(
            research_question=research_question,
            research_domain=research_domain,
            keywords=dataset_keywords,
            data_spec=data_spec,
        )
        search_query = build_external_search_query(field_context)
        if not search_query.strip():
            search_query = research_question or " ".join(dataset_keywords[:5])

        candidates: List[Dict[str, Any]] = []
        warnings: List[str] = []
        live_apis: List[str] = []

        zenodo = self._search_zenodo(search_query)
        if zenodo.get("error"):
            warnings.append(zenodo["error"])
        else:
            candidates.extend(zenodo.get("results", []))
            live_apis.append("zenodo")

        hf = self._search_huggingface(search_query)
        if hf.get("error"):
            warnings.append(hf["error"])
        else:
            candidates.extend(hf.get("results", []))
            live_apis.append("huggingface")

        fig = self._search_figshare(search_query)
        if fig.get("error"):
            warnings.append(fig["error"])
        else:
            candidates.extend(fig.get("results", []))
            live_apis.append("figshare")

        if should_search_biomedical_sources(field_context):
            pubmed_geo = self._search_pubmed_geo(search_query)
            if pubmed_geo.get("error"):
                warnings.append(pubmed_geo["error"])
            else:
                candidates.extend(pubmed_geo.get("results", []))
                live_apis.append("ncbi_geo")
        else:
            warnings.append(
                f"当前领域「{field_context.get('field')}」跳过 NCBI GEO 等生物医学数据源"
            )

        dedup: List[Dict[str, Any]] = []
        seen = set()
        for c in candidates:
            key = (c.get("dataset_name") or c.get("url") or "").lower()
            if key and key not in seen:
                seen.add(key)
                dedup.append(c)

        filtered = filter_relevant_external_candidates(dedup, field_context)
        if dedup and not filtered:
            warnings.append("外部检索命中条目但与当前研究领域相关性不足，已丢弃")
        if len(filtered) < len(dedup):
            warnings.append(
                f"已按领域过滤 {len(dedup) - len(filtered)} 条低相关外部数据候选"
            )

        result.data = {
            "candidates": filtered[:20],
            "count": len(filtered),
            "search_query": search_query,
            "research_field": field_context.get("field"),
            "offline_fallback": bool(warnings),
            "live_apis": live_apis,
            "registry_sources": ["huggingface", "zenodo", "figshare", "kaggle_catalog"],
        }
        result.warnings.extend(warnings)
        return result

    @staticmethod
    def _search_openalex(query: str) -> Dict[str, Any]:
        try:
            params = urllib.parse.urlencode({"search": query, "per_page": 5})
            url = f"https://api.openalex.org/works?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "AISci-DataFinder/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("results", [])[:5]:
                title = item.get("title") or ""
                doi = (item.get("doi") or "").replace("https://doi.org/", "")
                landing = item.get("primary_location", {}) or {}
                source_url = landing.get("landing_page_url") or item.get("id", "")
                results.append({
                    "source_platform": "OpenAlex",
                    "dataset_name": title[:200],
                    "url": source_url,
                    "doi": doi,
                    "description": "OpenAlex 论文/work 条目，可能含 data availability 链接",
                    "confidence": 0.55,
                    "availability": "metadata_only",
                    "import_supported": False,
                    "api_type": "metadata",
                })
            return {"results": results}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning(f"OpenAlex 检索失败: {exc}")
            return {"error": f"OpenAlex 不可用: {exc}", "results": []}
        except Exception as exc:
            return {"error": str(exc), "results": []}

    @staticmethod
    def _search_huggingface(query: str) -> Dict[str, Any]:
        try:
            params = urllib.parse.urlencode({"search": query, "limit": 5})
            url = f"https://huggingface.co/api/datasets?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "AISci-DataFinder/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in (data if isinstance(data, list) else [])[:5]:
                name = item.get("id") or item.get("name") or ""
                results.append({
                    "source_platform": "HuggingFace Datasets",
                    "dataset_name": name,
                    "url": f"https://huggingface.co/datasets/{name}",
                    "description": (item.get("description") or "")[:300],
                    "license": item.get("license") or "",
                    "confidence": 0.75,
                    "availability": "search_and_import",
                    "import_supported": True,
                })
            return {"results": results}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning(f"HuggingFace 检索失败: {exc}")
            return {"error": f"HuggingFace 不可用: {exc}", "results": []}
        except Exception as exc:
            return {"error": str(exc), "results": []}

    @staticmethod
    def _search_zenodo(query: str) -> Dict[str, Any]:
        try:
            params = urllib.parse.urlencode({"q": query, "size": 5, "type": "dataset"})
            url = f"https://zenodo.org/api/records?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "AISci-DataFinder/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = []
            for hit in (data.get("hits", {}).get("hits") or [])[:5]:
                meta = hit.get("metadata") or {}
                title = meta.get("title") or hit.get("title") or ""
                rec_id = hit.get("id") or ""
                results.append({
                    "source_platform": "Zenodo",
                    "dataset_name": title[:200],
                    "url": f"https://zenodo.org/record/{rec_id}" if rec_id else "",
                    "description": (meta.get("description") or "")[:300],
                    "license": (meta.get("license") or {}).get("id", "") if isinstance(meta.get("license"), dict) else str(meta.get("license") or ""),
                    "confidence": 0.72,
                    "availability": "url_only",
                    "import_supported": False,
                    "api_type": "live",
                })
            return {"results": results}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Zenodo 检索失败: %s", exc)
            return {"error": f"Zenodo 不可用: {exc}", "results": []}
        except Exception as exc:
            return {"error": str(exc), "results": []}

    @staticmethod
    def _search_figshare(query: str) -> Dict[str, Any]:
        try:
            from app.services.data_sources.repository_connector import _search_figshare

            fig = _search_figshare(query, limit=5)
            results = []
            for item in fig.get("results") or []:
                results.append({
                    "source_platform": "Figshare",
                    "dataset_name": item.get("dataset_name", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "license": str(item.get("license", "")),
                    "confidence": float(item.get("confidence", 0.68)),
                    "availability": "url_only",
                    "import_supported": False,
                    "api_type": "live",
                })
            if fig.get("error"):
                return {"error": fig["error"], "results": results}
            return {"results": results}
        except Exception as exc:
            logger.warning("Figshare 检索失败: %s", exc)
            return {"error": str(exc), "results": []}

    @staticmethod
    def _search_pubmed_geo(query: str) -> Dict[str, Any]:
        """NCBI E-utilities — GEO 数据集元数据（live API）。"""
        try:
            esearch_params = urllib.parse.urlencode({
                "db": "gds",
                "term": f"{query}[All Fields] AND gse[Entry Type]",
                "retmax": 5,
                "retmode": "json",
            })
            esearch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{esearch_params}"
            req = urllib.request.Request(esearch_url, headers={"User-Agent": "AISci-DataFinder/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                es_data = json.loads(resp.read().decode("utf-8"))
            ids = (es_data.get("esearchresult") or {}).get("idlist") or []
            if not ids:
                return {"results": []}

            esummary_params = urllib.parse.urlencode({
                "db": "gds",
                "id": ",".join(ids[:5]),
                "retmode": "json",
            })
            esummary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{esummary_params}"
            req2 = urllib.request.Request(esummary_url, headers={"User-Agent": "AISci-DataFinder/1.0"})
            with urllib.request.urlopen(req2, timeout=REQUEST_TIMEOUT) as resp2:
                sum_data = json.loads(resp2.read().decode("utf-8"))

            results = []
            result_map = (sum_data.get("result") or {})
            for gid in ids[:5]:
                item = result_map.get(gid) or {}
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("gse") or f"GEO {gid}"
                gse = item.get("gse") or ""
                results.append({
                    "source_platform": "NCBI GEO",
                    "dataset_name": str(title)[:200],
                    "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse}" if gse else "",
                    "description": (item.get("summary") or "GEO 表达/芯片数据集元数据")[:300],
                    "confidence": 0.68,
                    "availability": "metadata_only",
                    "import_supported": False,
                    "api_type": "metadata",
                    "geo_id": gse,
                })
            return {"results": results}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("NCBI GEO 检索失败: %s", exc)
            return {"error": f"NCBI GEO 不可用: {exc}", "results": []}
        except Exception as exc:
            return {"error": str(exc), "results": []}
