"""证据链推理共享工具"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple


COUNTER_KEYWORDS = [
    "limitation", "failure", "negative result", "does not improve",
    "challenge", "drawback", "risk", "contradict", "unable", "failed",
    "限制", "失败", "未提升", "挑战", "风险", "不足", "contrary",
]

PLACEHOLDER_TITLES = {
    "unknown", "placeholder", "tbd", "anonymous", "待补充", "vit paper",
}


def new_evidence_id() -> str:
    return f"ev_{uuid.uuid4().hex[:12]}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def tokenize(text: str) -> Set[str]:
    return {t for t in re.findall(r"[\w\u4e00-\u9fff]+", normalize_text(text)) if len(t) >= 2}


def score_relevance(query: str, text: str) -> float:
    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0
    t_tokens = tokenize(text)
    if not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return round(min(1.0, overlap / max(len(q_tokens), 1) * 1.2), 4)


def is_verifiable_source(fact: Dict[str, Any], citation_map: List[Dict[str, Any]]) -> bool:
    title = (fact.get("source_paper_title") or fact.get("title") or "").strip()
    doc_id = fact.get("document_id") or fact.get("source_document_id")
    chunk_id = fact.get("source_chunk_id") or fact.get("chunk_id")
    paper_id = fact.get("paper_id") or fact.get("external_id")

    if doc_id or chunk_id or paper_id:
        return True
    if title and normalize_text(title) not in PLACEHOLDER_TITLES and len(title) >= 8:
        return True

    title_l = normalize_text(title)
    for cit in citation_map or []:
        cit_title = normalize_text(cit.get("paper_title") or cit.get("title") or "")
        if cit_title and (cit_title in title_l or title_l in cit_title):
            return True
    return False


def fact_to_evidence(
    fact: Dict[str, Any],
    stance: str,
    hypothesis: str,
    citation_map: Optional[List[Dict[str, Any]]] = None,
    used_in_revision: bool = False,
) -> Optional[Dict[str, Any]]:
    if not is_verifiable_source(fact, citation_map or []):
        return None

    title = fact.get("source_paper_title") or fact.get("title") or ""
    doc_id = fact.get("document_id") or fact.get("source_document_id") or ""
    content = fact.get("content") or fact.get("fact_text") or fact.get("quote_text") or ""
    quote = fact.get("quote_text") or content[:300]

    source_type = "paper"
    if doc_id:
        source_type = "uploaded_pdf"
    for cit in citation_map or []:
        if cit.get("document_id") == doc_id:
            st = cit.get("source_type", "")
            if st in {"bibtex", "arxiv", "paper", "uploaded_pdf"}:
                source_type = st if st != "arxiv" else "paper"
            break

    rel = score_relevance(hypothesis, f"{content} {title}")
    reliability = 0.85 if fact.get("source_chunk_id") or fact.get("chunk_id") else 0.7
    if doc_id:
        reliability += 0.05

    return {
        "evidence_id": fact.get("fact_id") or new_evidence_id(),
        "claim": content[:500],
        "stance": stance,
        "source_title": title,
        "source_type": source_type,
        "year": fact.get("year"),
        "doi": fact.get("doi", ""),
        "arxiv_id": fact.get("arxiv_id") or fact.get("external_id", ""),
        "paper_id": fact.get("paper_id") or doc_id or "",
        "quote_or_summary": quote[:500],
        "relevance_score": rel,
        "reliability_score": round(min(1.0, reliability), 4),
        "used_in_revision": used_in_revision,
    }


def build_verified_source_index(
    literature_mining: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    facts = literature_mining.get("facts", []) or []
    citation_map = literature_mining.get("citation_map", []) or []
    imported = literature_mining.get("imported_documents", []) or []
    retrieved = literature_mining.get("retrieved_papers", []) or []
    return facts, citation_map, imported + retrieved
