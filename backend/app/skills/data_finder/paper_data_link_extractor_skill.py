"""论文数据链接抽取 Skill"""
from __future__ import annotations

from typing import Any, Dict, List

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import (
    DATA_KEYWORDS,
    detect_figures_in_text,
    detect_tables_in_text,
    extract_urls,
)


class PaperDataLinkExtractorSkill(BaseSkill):
    name = "PaperDataLinkExtractor"
    description = "从论文 PDF/BibTeX 文本抽取数据链接与表图引用"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        documents = input_data.get("documents", []) or []
        extractions: List[Dict[str, Any]] = []

        for doc in documents:
            text = " ".join([
                doc.get("raw_text") or "",
                doc.get("abstract") or "",
                doc.get("title") or "",
            ])
            urls = extract_urls(text)
            data_links = [u for u in urls if any(k in u.lower() for k in (
                "zenodo", "figshare", "dryad", "kaggle", "huggingface", "dataset", "data"
            ))]
            code_links = [u for u in urls if "github.com" in u.lower()]
            supp_links = [u for u in urls if any(k in text.lower() for k in (
                "supplementary", "supplement", "appendix", "补充材料"
            )) and u in urls]

            tables = detect_tables_in_text(text)
            figures = detect_figures_in_text(text)

            keyword_hits = sum(1 for kw in DATA_KEYWORDS if kw in text.lower())
            confidence = min(1.0, 0.3 + 0.1 * len(data_links) + 0.05 * len(tables) + 0.02 * keyword_hits)

            extractions.append({
                "paper_id": doc.get("id") or doc.get("document_id", ""),
                "source_title": doc.get("title") or doc.get("filename", ""),
                "data_links": data_links,
                "code_links": code_links,
                "supplementary_links": supp_links or [u for u in urls if "supplement" in u.lower()],
                "tables_detected": tables,
                "figures_detected": figures,
                "confidence": round(confidence, 4),
            })

        result.data = {"paper_extractions": extractions, "count": len(extractions)}
        return result
