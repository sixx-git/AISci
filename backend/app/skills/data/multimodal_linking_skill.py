"""
多模态数据关联 Skill
将文献事实、实验数据、历史数据库进行关联，输出 Evidence 证据链，支持假设生成。
"""
import logging
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class MultimodalDataLinkingSkill(BaseSkill):
    """多模态数据关联 Skill

    输入:
      - literature_facts: List[dict]     文献提取的事实
      - multimodal_datasets: List[dict]  多模态数据集
      - reference_db: List[dict]         历史/参考数据库（可选）
      - hypothesis: str                  待验证假设（可选）

    输出 (SkillResult.data):
      - evidence: List[dict]             关联证据，每条证据含 source_type、confidence、linked_fact_ids
      - links: List[dict]                数据关联关系
      - evidence_summary: dict           证据链概览
      - linked_keywords: List[str]       关联关键词
    """

    name = "MultimodalDataLinking"
    description = "关联文献事实、实验数据与历史数据库，输出结构化 Evidence 支持假设生成"
    source_reference = "AI Scientist (arxiv:2408.06292) — evidence linking & data grounding 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        literature_facts = input_data.get("literature_facts", [])
        multimodal_datasets = input_data.get("multimodal_datasets", [])
        reference_db = input_data.get("reference_db", [])
        hypothesis = input_data.get("hypothesis", "")

        if not literature_facts and not multimodal_datasets:
            result.add_warning("无文献事实或数据集可供关联")
            result.data = {
                "evidence": [],
                "links": [],
                "evidence_summary": {"total_evidence": 0, "by_source_type": {}},
                "linked_keywords": [],
            }
            return result

        evidence_list: List[dict] = []
        links: List[dict] = []
        linked_keywords: set = set()

        ds_keywords = self._extract_dataset_keywords(multimodal_datasets)
        linked_keywords.update(ds_keywords)

        for fact in literature_facts:
            fact_id = fact.get("fact_id", hashlib.md5(str(fact).encode()).hexdigest()[:12])
            fact_text = fact.get("content", "") or fact.get("text", "")
            fact_keywords = fact.get("keywords", [])
            linked_keywords.update(fact_keywords)

            related_datasets = self._find_related_datasets(fact_text, multimodal_datasets)

            evidence_entry = {
                "evidence_id": hashlib.md5(
                    f"{fact_id}:{datetime.now().isoformat()}".encode()
                ).hexdigest()[:12],
                "source_type": "literature",
                "source_id": fact_id,
                "fact_content": fact_text[:500],
                "confidence": fact.get("confidence", 0.7),
                "linked_dataset_ids": [ds.get("file_id") for ds in related_datasets],
                "linked_keywords": list(
                    set(fact_keywords) | set(self._extract_dataset_keywords(related_datasets))
                ),
                "hypothesis_relation": self._compute_hypothesis_relation(
                    hypothesis, fact_text, ds_keywords
                ),
            }
            evidence_list.append(evidence_entry)

            for ds in related_datasets:
                link = {
                    "link_id": hashlib.md5(
                        f"{fact_id}:{ds.get('file_id', '')}".encode()
                    ).hexdigest()[:12],
                    "source_type": "literature",
                    "source_id": fact_id,
                    "target_type": "dataset",
                    "target_id": ds.get("file_id", ""),
                    "relation": "supports" if evidence_entry["hypothesis_relation"]["related"] else "references",
                    "common_keywords": list(
                        set(fact_keywords) & set(self._extract_dataset_keywords([ds]))
                    ),
                }
                links.append(link)

        for ref_entry in reference_db:
            ref_id = ref_entry.get("id", hashlib.md5(str(ref_entry).encode()).hexdigest()[:12])
            ref_text = ref_entry.get("description", "") or ref_entry.get("content", "")
            ref_keywords = ref_entry.get("keywords", [])
            linked_keywords.update(ref_keywords)

            related_datasets = self._find_related_datasets(ref_text, multimodal_datasets)
            evidence_entry = {
                "evidence_id": hashlib.md5(
                    f"{ref_id}:ref:{datetime.now().isoformat()}".encode()
                ).hexdigest()[:12],
                "source_type": "reference_database",
                "source_id": ref_id,
                "fact_content": ref_text[:500],
                "confidence": ref_entry.get("confidence", 0.6),
                "linked_dataset_ids": [ds.get("file_id") for ds in related_datasets],
                "linked_keywords": list(
                    set(ref_keywords) | set(self._extract_dataset_keywords(related_datasets))
                ),
                "hypothesis_relation": self._compute_hypothesis_relation(
                    hypothesis, ref_text, ds_keywords
                ),
            }
            evidence_list.append(evidence_entry)

            for ds in related_datasets:
                link = {
                    "link_id": hashlib.md5(
                        f"{ref_id}:{ds.get('file_id', '')}".encode()
                    ).hexdigest()[:12],
                    "source_type": "reference_database",
                    "source_id": ref_id,
                    "target_type": "dataset",
                    "target_id": ds.get("file_id", ""),
                    "relation": "grounds",
                    "common_keywords": list(
                        set(ref_keywords) & set(self._extract_dataset_keywords([ds]))
                    ),
                }
                links.append(link)

        by_source = {}
        for e in evidence_list:
            st = e["source_type"]
            by_source[st] = by_source.get(st, 0) + 1

        evidence_summary = {
            "total_evidence": len(evidence_list),
            "total_links": len(links),
            "by_source_type": by_source,
            "high_confidence_count": sum(1 for e in evidence_list if e.get("confidence", 0) >= 0.7),
            "hypothesis_related_count": sum(1 for e in evidence_list if e.get("hypothesis_relation", {}).get("related", False)),
        }

        result.data = {
            "evidence": evidence_list,
            "links": links,
            "evidence_summary": evidence_summary,
            "linked_keywords": sorted(linked_keywords),
        }
        result.metadata = {
            "facts_count": len(literature_facts),
            "datasets_count": len(multimodal_datasets),
            "reference_entries": len(reference_db),
            "linked_at": datetime.now().isoformat(),
        }
        return result

    @staticmethod
    def _extract_dataset_keywords(datasets: List[dict]) -> List[str]:
        keywords = []
        for ds in datasets:
            cols = ds.get("columns", [])
            keywords.extend(cols[:10])
            file_name = ds.get("file_name", "")
            if file_name:
                keywords.append(file_name)
        return list(set(keywords))

    @staticmethod
    def _find_related_datasets(fact_text: str, datasets: List[dict]) -> List[dict]:
        related = []
        fact_lower = fact_text.lower()
        for ds in datasets:
            score = 0
            cols = ds.get("columns", [])
            for col in cols:
                if col.lower() in fact_lower:
                    score += 1
            file_name = ds.get("file_name", "").lower()
            if file_name and file_name.split(".")[0] in fact_lower:
                score += 2
            if score >= 1:
                ds_copy = {k: v for k, v in ds.items() if k not in ("sample_data",)}
                ds_copy["_relation_score"] = score
                related.append(ds_copy)
        return sorted(related, key=lambda x: x.get("_relation_score", 0), reverse=True)

    @staticmethod
    def _compute_hypothesis_relation(
        hypothesis: str, fact_text: str, dataset_keywords: List[str]
    ) -> Dict[str, Any]:
        if not hypothesis:
            return {"related": False, "score": 0.0}
        hypo_lower = hypothesis.lower()
        fact_lower = fact_text.lower()
        score = 0.0

        hypo_tokens = set(hypo_lower.split())
        fact_tokens = set(fact_lower.split())
        common_tokens = hypo_tokens & fact_tokens
        if hypo_tokens:
            score = len(common_tokens) / len(hypo_tokens)

        kw_matches = sum(1 for kw in dataset_keywords if kw.lower() in hypo_lower)
        if dataset_keywords:
            score = max(score, kw_matches / len(dataset_keywords))

        return {"related": score > 0.1, "score": round(min(score, 1.0), 4)}