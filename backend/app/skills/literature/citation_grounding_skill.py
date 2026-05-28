"""
引用接地 Skill
参考能力：OpenScholar citation-backed synthesis
——检查 References 是否来自真实 Document / Evidence / citation_map，
自动拒绝 LLM 自造引用，输出风险等级。
"""
import logging
import re
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class CitationGroundingSkill(BaseSkill):
    """引用接地验证 Skill

    输入:
      - references: List[str]              报告中的参考文献列表
      - citation_map: List[dict]           LiteratureMiningAgent 输出的 citation_map
      - literature_facts: List[dict]       LiteratureMiningAgent 输出的 facts

    输出 (SkillResult.data):
      - verified_references: List[str]      通过验证的引用
      - incomplete_references: List[str]    格式不完整的引用（无作者/年份/DOI）
      - rejected_references: List[str]      无法验证、可能虚构的引用
      - risk_level: str                     low / medium / high
      - verification_summary: str           简要说明
    """

    name = "CitationGrounding"
    description = "校验 References 是否可追溯至真实文献，拒绝 LLM 自造引用"
    source_reference = "OpenScholar (arxiv:2401.xxxxx) — citation-backed synthesis 能力参考"

    _KNOWN_HALLUCINATION_PATTERNS = [
        re.compile(r"^\[\d+\]\s*$"),
        re.compile(r"^\(Anonymous,\s*\d{4}\)$"),
        re.compile(r"^\(Unknown\s*Author.*\)$", re.IGNORECASE),
    ]

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)

        references: List[str] = input_data.get("references", [])
        citation_map: List[dict] = input_data.get("citation_map", [])
        literature_facts: List[dict] = input_data.get("literature_facts", [])

        if not references:
            result.add_warning("报告 References 为空，建议补充文献引用")
            result.data = {
                "verified_references": [],
                "incomplete_references": [],
                "rejected_references": [],
                "risk_level": "high",
                "verification_summary": "Report contains no references.",
            }
            return result

        verified_keys = self._build_verified_keys(citation_map, literature_facts)
        incomplete_keys = self._extract_citation_keys(references)

        verified: List[str] = []
        incomplete: List[str] = []
        rejected: List[str] = []

        for ref in references:
            if not isinstance(ref, str) or not ref.strip():
                rejected.append(ref or "(empty)")
                continue

            if self._match_hallucination_pattern(ref):
                rejected.append(ref)
                continue

            matched = self._try_match(ref, verified_keys)
            if matched:
                verified.append(ref)
                continue

            if self._has_minimal_metadata(ref):
                incomplete.append(ref)
            else:
                rejected.append(ref)

        risk = self._assess_risk(verified, incomplete, rejected, total=len(references))

        result.data = {
            "verified_references": verified,
            "incomplete_references": incomplete,
            "rejected_references": rejected,
            "risk_level": risk,
            "verification_summary": (
                f"{len(verified)} verified, {len(incomplete)} incomplete, "
                f"{len(rejected)} rejected (risk: {risk})"
            ),
        }
        result.metadata = {
            "total_references": len(references),
            "verified_count": len(verified),
            "rejected_count": len(rejected),
            "incomplete_count": len(incomplete),
            "verified_keys_count": len(verified_keys),
        }

        if risk == "high":
            result.add_warning("引用风险级别 HIGH — 多数引用无法在文献库中验证")
        elif risk == "medium":
            result.add_warning("部分引用未能完全验证，建议人工复核")

        return result

    @staticmethod
    def _build_verified_keys(citation_map: List[dict], facts: List[dict]) -> Set[str]:
        keys: Set[str] = set()
        for cit in citation_map:
            for field in ("paper_title", "title", "authors", "doi", "external_id", "source_url"):
                val = cit.get(field, "")
                if isinstance(val, str) and len(val.strip()) >= 5:
                    keys.add(val.strip().lower())
            authors = cit.get("authors", "")
            if isinstance(authors, str):
                for a in authors.split(","):
                    a = a.strip()
                    if len(a) >= 3:
                        keys.add(a.lower())
        for fact in facts:
            title = fact.get("source_paper_title", "")
            if title:
                keys.add(title.lower())
            chunk = fact.get("chunk_id", "")
            if chunk:
                keys.add(chunk)
        return keys

    def _match_hallucination_pattern(self, ref: str) -> bool:
        ref_stripped = ref.strip()
        for pat in self._KNOWN_HALLUCINATION_PATTERNS:
            if pat.match(ref_stripped):
                return True
        # 引用长度极短且无有效信息
        if len(ref_stripped) < 10:
            return True
        return False

    @staticmethod
    def _try_match(ref: str, keys: Set[str]) -> bool:
        ref_lower = ref.lower()
        for kw in keys:
            if len(kw) >= 6 and kw in ref_lower:
                return True
        return False

    @staticmethod
    def _has_minimal_metadata(ref: str) -> bool:
        tokens = ref.lower().split()
        has_author = any(len(t) >= 1 and t[0].isupper() for t in tokens)
        has_year = bool(re.search(r"\b(19|20)\d{2}[a-z]?\b", ref))
        has_doi = "doi" in ref.lower() or "arxiv" in ref.lower()
        return has_author and has_year or has_doi

    @staticmethod
    def _extract_citation_keys(refs: List[str]) -> List[str]:
        keys = []
        for ref in refs:
            if not isinstance(ref, str):
                continue
            m = re.search(r"\b(19|20)\d{2}[a-z]?\b", ref)
            if m:
                parts = ref[:m.start()].split(",")
                if parts:
                    keys.append(parts[0].strip().lower())
            doi = re.search(r"(?:doi|arxiv)[:\s]*([^\s]+)", ref, re.IGNORECASE)
            if doi:
                keys.append(doi.group(1).strip(".").lower())
        return keys

    @staticmethod
    def _assess_risk(verified: list, incomplete: list, rejected: list, total: int) -> str:
        if total == 0:
            return "high"
        rejected_ratio = len(rejected) / total
        verified_ratio = len(verified) / total
        if rejected_ratio > 0.6 or verified_ratio < 0.2:
            return "high"
        if rejected_ratio > 0.3 or verified_ratio < 0.5:
            return "medium"
        return "low"