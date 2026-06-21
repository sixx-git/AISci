"""外部数据集检索 Skill"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.data.dataset_discovery_skill import KNOWN_DATASETS, DatasetDiscoverySkill

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 12


class ExternalDatasetSearchSkill(BaseSkill):
    name = "ExternalDatasetSearch"
    description = "从 OpenAlex/HuggingFace/Kaggle 等平台检索候选数据源"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        research_question = input_data.get("research_question", "")
        dataset_keywords = input_data.get("dataset_keywords", []) or []
        query = research_question or " ".join(dataset_keywords[:5])

        candidates: List[Dict[str, Any]] = []
        warnings: List[str] = []

        discovery = DatasetDiscoverySkill()
        disc_res = await discovery.run(
            {"research_question": query, "keywords": dataset_keywords, "max_results": 8},
            context,
        )
        if disc_res.data.get("datasets"):
            for ds in disc_res.data["datasets"]:
                candidates.append({
                    "source_platform": ds.get("source", "known_catalog"),
                    "dataset_name": ds.get("dataset_name", ""),
                    "url": ds.get("url", ""),
                    "description": ds.get("description", ""),
                    "license": ds.get("license", ""),
                    "confidence": 0.7,
                })

        openalex = self._search_openalex(query)
        if openalex.get("error"):
            warnings.append(openalex["error"])
        else:
            candidates.extend(openalex.get("results", []))

        hf = self._search_huggingface(query)
        if hf.get("error"):
            warnings.append(hf["error"])
        else:
            candidates.extend(hf.get("results", []))

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
        }
        result.warnings.extend(warnings)
        result.warnings.extend(disc_res.warnings)
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
