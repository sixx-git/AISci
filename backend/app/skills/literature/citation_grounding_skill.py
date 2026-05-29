"""
引用接地 Skill
参考能力：PaperQA / PaperQA2、OpenScholar citation-backed synthesis
——检查每条 reference 是否来自真实 Document / Evidence / citation_map，
自动拒绝 LLM 自造引用、unknown 作者、placeholder、空引用，输出风险等级。
"""
import logging
import re
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

PREFIX_PATTERNS = [
    re.compile(r"^\[(\d+)\]\s*$"),
    re.compile(r"^\(\d+\)\s*$"),
    re.compile(r"^\d+\.\s*$"),
]

PLACEHOLDER_PATTERNS = [
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"TBD", re.IGNORECASE),
    re.compile(r"to\s+be\s+(determined|added|filled)", re.IGNORECASE),
    re.compile(r"待(补充|填|定|加)", re.IGNORECASE),
    re.compile(r"etc\.?\s*$", re.IGNORECASE),
]

ANONYMOUS_PATTERNS = [
    re.compile(r"^\(Anonymous[,\s]*\d{4}\)$"),
    re.compile(r"^Anonymous[,\s]+\d{4}"),
    re.compile(r"^\(Unknown\s*Author.*\)$", re.IGNORECASE),
    re.compile(r"^Unknown\s+Author", re.IGNORECASE),
    re.compile(r"Anon\.?\s*(19|20)\d{2}", re.IGNORECASE),
]

LLM_FABRICATION_PATTERNS = [
    re.compile(r"^\[(Citation\s*)?[Nn]eeded\]$"),
    re.compile(r"^\([Nn]o\s+[Ss]ource\)$"),
    re.compile(r"^(Source|Ref|Reference):\s*$"),
    re.compile(r"^见\s*(上文|前述|上述|XXX)", re.IGNORECASE),
    re.compile(r"^同上"),
    re.compile(r"^(et\s+al\.?\s*,?\s*)?(19|20)\d{2}[a-z]?\s*[，,]\s*$"),
    re.compile(r"\bViT\s+(Paper|Model|论文)\b", re.IGNORECASE),
    re.compile(r"\bCross-modal\s+(Paper|Model|论文)\b", re.IGNORECASE),
    re.compile(r"\bLLM\s*(自造|生成|hallucinat)", re.IGNORECASE),
    re.compile(r"\b(fabricated|made.?up|non.?existent)\s+(reference|citation|paper)\b", re.IGNORECASE),
]


class CitationGroundingSkill(BaseSkill):
    """引用接地验证 Skill

    输入（兼容多种上游键名）:
      - references: List[str]              报告中的参考文献列表
      - draft_references: List[str]        LLM 草稿中的引用列表（备选键名）
      - citation_map: List[dict]           LiteratureMiningAgent 输出的 citation_map
      - literature_facts: List[dict]       LiteratureMiningAgent 输出的 facts
      - documents: List[dict]             已上传/已录入的文献文档元数据
      - evidence_facts: List[dict]        封装的证据事实（含 source_paper_title）
      - verified_references: List[dict]   上游预验证的引用列表

    输出 (SkillResult.data):
      - verified_references: List[dict]    通过验证的引用（含 meta）
      - incomplete_references: List[dict]  格式不完整的引用（无作者/年份/DOI）
      - rejected_references: List[dict]    无法验证、可能虚构的引用
      - risk_level: str                    low / medium / high
      - verification_summary: str          简要说明
      - rejection_reasons: dict            key=ref_index → reason
    """

    name = "CitationGrounding"
    description = "校验 References 是否可追溯至真实文献，拒绝 LLM 自造引用"
    source_reference = "PaperQA / PaperQA2 (arxiv:2312.07559) — citation-backed verification; OpenScholar — citation-backed synthesis 能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        references: List[str] = (
            input_data.get("references")
            or input_data.get("draft_references")
            or []
        )
        citation_map: List[dict] = input_data.get("citation_map", [])
        literature_facts: List[dict] = (
            input_data.get("literature_facts")
            or input_data.get("evidence_facts")
            or []
        )
        documents: List[dict] = input_data.get("documents", [])
        pre_verified: List[dict] = input_data.get("verified_references", [])

        if not references:
            result.add_warning("报告 References 为空，建议补充文献引用")
            result.data = {
                "verified_references": [],
                "incomplete_references": [],
                "rejected_references": [],
                "risk_level": "high",
                "verification_summary": "Report contains no references.",
                "rejection_reasons": {},
            }
            return result

        verified_keys = self._build_verified_keys(
            citation_map, literature_facts, documents, pre_verified
        )

        verified: List[dict] = []
        incomplete: List[dict] = []
        rejected: List[dict] = []
        rejection_reasons: Dict[int, str] = {}

        enriched_references = [self._normalize_ref(r, i) for i, r in enumerate(references) if r]

        for ref_meta in enriched_references:
            idx = ref_meta["index"]
            ref_text = ref_meta["text"]
            ref_lower = ref_text.lower()

            if self._match_prefix_only(ref_text):
                rejected.append(ref_meta)
                rejection_reasons[idx] = "empty_prefix"
                continue

            if self._match_placeholder(ref_text):
                rejected.append(ref_meta)
                rejection_reasons[idx] = "placeholder"
                continue

            if self._match_anonymous(ref_text):
                rejected.append(ref_meta)
                rejection_reasons[idx] = "anonymous_author"
                continue

            if self._match_llm_fabrication(ref_text):
                rejected.append(ref_meta)
                rejection_reasons[idx] = "llm_fabrication"
                continue

            if self._try_match(ref_text, verified_keys):
                verified.append(ref_meta)
                continue

            if self._has_minimal_metadata(ref_text):
                verification_hint = self._build_verification_hint(ref_text, verified_keys)
                ref_meta["verification_hint"] = verification_hint
                incomplete.append(ref_meta)
            else:
                rejection_reasons[idx] = "unverifiable"
                rejected.append(ref_meta)

        risk = self._assess_risk(verified, incomplete, rejected, total=len(references))

        verified_sources_count = len(verified_keys) + len(pre_verified)

        result.data = {
            "verified_references": [r.get("text", "") for r in verified],
            "verified_references_detail": verified,
            "incomplete_references": [r.get("text", "") for r in incomplete],
            "incomplete_references_detail": incomplete,
            "rejected_references": [r.get("text", "") for r in rejected],
            "rejected_references_detail": rejected,
            "references_verified": len(verified),
            "risk_level": risk,
            "verification_summary": (
                f"{len(verified)} verified, {len(incomplete)} incomplete, "
                f"{len(rejected)} rejected of {len(references)} total "
                f"(risk: {risk}, verified sources: {verified_sources_count})"
            ),
            "rejection_reasons": rejection_reasons,
        }
        result.metadata = {
            "total_references": len(references),
            "verified_count": len(verified),
            "rejected_count": len(rejected),
            "incomplete_count": len(incomplete),
            "verified_keys_count": len(verified_keys),
            "verified_sources_count": verified_sources_count,
        }

        if risk == "high":
            result.add_warning("引用风险级别 HIGH — 多数引用无法在文献库中验证，疑似 LLM 自造")
        elif risk == "medium":
            result.add_warning("部分引用未能完全验证，建议人工复核")

        return result

    # ────────────── Key Building ──────────────

    @staticmethod
    def _build_verified_keys(
        citation_map: List[dict],
        facts: List[dict],
        documents: List[dict],
        pre_verified: List[dict],
    ) -> Set[str]:
        keys: Set[str] = set()

        for cit in citation_map:
            for field in (
                "paper_title", "title",
                "authors",
                "doi",
                "external_id",
                "source_url",
            ):
                val = cit.get(field, "")
                if isinstance(val, str) and len(val.strip()) >= 4:
                    keys.add(val.strip().lower())
            authors = cit.get("authors", "")
            if isinstance(authors, str):
                for a in authors.split(","):
                    a = a.strip()
                    if len(a) >= 3:
                        keys.add(a.lower())
            if isinstance(authors, list):
                for a in authors:
                    if isinstance(a, str) and len(a.strip()) >= 3:
                        keys.add(a.strip().lower())

        for fact in facts:
            for field in ("source_paper_title", "paper_title", "title", "fact_id", "chunk_id"):
                val = fact.get(field, "")
                if isinstance(val, str) and len(val) >= 4:
                    keys.add(val.lower())
            content = fact.get("content", "") or fact.get("fact_text", "")
            if isinstance(content, str) and len(content) >= 20:
                tokens = content.lower().split()
                keys.update(w for w in tokens if len(w) >= 6)

        for doc in documents:
            for field in ("title", "authors", "doi", "filename", "external_id"):
                val = doc.get(field, "")
                if isinstance(val, str) and len(val.strip()) >= 3:
                    keys.add(val.strip().lower())

        for pv in pre_verified:
            for field in ("paper_title", "title", "authors", "doi", "external_id"):
                val = pv.get(field, "")
                if isinstance(val, str) and len(val.strip()) >= 4:
                    keys.add(val.strip().lower())

        return keys

    # ────────────── Normalization ──────────────

    @staticmethod
    def _normalize_ref(ref_text: str, idx: int) -> dict:
        """标准化引用文本，返回带索引和清洗后文本的 dict"""
        text = ref_text.strip()
        text = re.sub(r"\s+", " ", text)
        return {"index": idx, "text": text}

    # ────────────── Pattern Matching ──────────────

    @staticmethod
    def _match_prefix_only(ref: str) -> bool:
        for pat in PREFIX_PATTERNS:
            if pat.match(ref.strip()):
                return True
        return len(ref.strip()) < 10

    @staticmethod
    def _match_placeholder(ref: str) -> bool:
        for pat in PLACEHOLDER_PATTERNS:
            if pat.search(ref):
                return True
        return False

    @staticmethod
    def _match_anonymous(ref: str) -> bool:
        for pat in ANONYMOUS_PATTERNS:
            if pat.match(ref.strip()) or pat.search(ref):
                return True
        return False

    @staticmethod
    def _match_llm_fabrication(ref: str) -> bool:
        for pat in LLM_FABRICATION_PATTERNS:
            if pat.match(ref.strip()) or pat.search(ref):
                return True
        return False

    # ────────────── Verification ──────────────

    @staticmethod
    def _try_match(ref: str, keys: Set[str]) -> bool:
        ref_lower = ref.lower()
        for kw in keys:
            if len(kw) >= 5 and kw in ref_lower:
                return True
        doi_match = re.search(r"(10\.\d{4,}/[^\s]+)", ref)
        if doi_match:
            doi = doi_match.group(1).strip(".,;)]").lower()
            return doi in keys
        arxiv_match = re.search(r"arxiv[:\s]*([\d.]+v?\d*)", ref, re.IGNORECASE)
        if arxiv_match:
            arxiv = arxiv_match.group(1).strip().lower()
            return arxiv in keys
        return False

    @staticmethod
    def _has_minimal_metadata(ref: str) -> bool:
        tokens = ref.lower().split()
        has_capital = any(len(t) > 0 and t[0].isupper() for t in tokens if len(t) >= 2)
        has_year = bool(re.search(r"\b(19|20)\d{2}[a-z]?\b", ref))
        has_doi = bool(re.search(r"(10\.\d{4,}/)", ref))
        has_arxiv = "arxiv" in ref.lower()
        has_title_marker = bool(re.search(r'"([^"]{20,})"', ref))
        has_venue = bool(re.search(
            r"\b(journal|conference|proceedings|symposium|transaction|letter|review)\b",
            ref, re.IGNORECASE,
        ))
        score = sum([has_capital, has_year, has_doi or has_arxiv, has_title_marker or has_venue])
        return score >= 2

    @staticmethod
    def _build_verification_hint(ref: str, keys: Set[str]) -> str:
        ref_lower = ref.lower()
        hints = []
        for kw in keys:
            if len(kw) >= 4 and kw in ref_lower:
                hints.append(kw[:60])
        return "; ".join(hints[:3]) if hints else "no matching source found"

    # ────────────── Risk Assessment ──────────────

    @staticmethod
    def _assess_risk(
        verified: list,
        incomplete: list,
        rejected: list,
        total: int,
    ) -> str:
        if total == 0:
            return "high"
        rejected_ratio = len(rejected) / total
        verified_ratio = len(verified) / total
        if rejected_ratio > 0.6 or verified_ratio < 0.2:
            return "high"
        if rejected_ratio > 0.3 or verified_ratio < 0.5:
            return "medium"
        return "low"