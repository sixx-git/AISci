"""外部数据集检索 Skill"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 12


class ExternalDatasetSearchSkill(BaseSkill):
    name = "ExternalDatasetSearch"
    description = "从 OpenAlex / NCBI GEO 检索元数据候选（HF/Zenodo/Kaggle 由 registry 负责）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = input_data.get("research_question", "")
        dataset_keywords = input_data.get("dataset_keywords", []) or []
        query = research_question or " ".join(dataset_keywords[:5])

        candidates: List[Dict[str, Any]] = []
        warnings: List[str] = []

        openalex = self._search_openalex(query)
        if openalex.get("error"):
            warnings.append(openalex["error"])
        else:
            candidates.extend(openalex.get("results", []))

        pubmed_geo = self._search_pubmed_geo(query)
        if pubmed_geo.get("error"):
            warnings.append(pubmed_geo["error"])
        else:
            candidates.extend(pubmed_geo.get("results", []))

        if not candidates:
            warnings.append("无法联网或未命中外部数据源，已优先使用本地 PDF/BibTeX 抽取结果")

        dedup: List[Dict[str, Any]] = []
        seen = set()
        for c in candidates:
            key = (c.get("dataset_name") or c.get("url") or "").lower()
            if key and key not in seen:
                seen.add(key)
                dedup.append(c)

        result.data = {
            "candidates": dedup[:20],
            "count": len(dedup),
            "offline_fallback": bool(warnings),
            "live_apis": ["openalex", "ncbi_geo"],
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
                    "api_type": "live",
                })
            return {"results": results}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Zenodo 检索失败: %s", exc)
            return {"error": f"Zenodo 不可用: {exc}", "results": []}
        except Exception as exc:
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
