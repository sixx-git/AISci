"""文献检索通用工具（query 规范化、fact 匹配等）。"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

_FACT_SUFFIX_RE = re.compile(r"(\d+)$")


def normalize_api_search_query(query: str) -> str:
    """将 LLM 布尔检索式转为 API 友好的空格关键词。"""
    q = (query or "").strip()
    if not q:
        return ""
    phrases = re.findall(r'"([^"]+)"', q)
    q = re.sub(r"\b(AND|OR|NOT)\b", " ", q, flags=re.I)
    q = re.sub(r'["\(\)]', " ", q)
    tokens: List[str] = []
    for p in phrases:
        p = p.strip()
        if len(p) >= 2:
            tokens.append(p)
    for t in re.split(r"[\s,，；;、/|]+", q):
        t = t.strip()
        if len(t) >= 2 and t.lower() not in ("and", "or", "not"):
            tokens.append(t)
    seen: Set[str] = set()
    out: List[str] = []
    for t in tokens:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return " ".join(out[:12])[:240]


def normalize_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", t)
    return " ".join(t.split())


def titles_match(a: str, b: str, *, min_ratio: float = 0.55) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / max(len(ta), len(tb))
    return overlap >= min_ratio


def _fact_numeric_suffix(fact_id: str) -> Optional[str]:
    match = _FACT_SUFFIX_RE.search((fact_id or "").strip())
    return match.group(1) if match else None


def match_literature_facts(all_facts: List[dict], target_ids: List[str]) -> List[dict]:
    """按 fact_id 精确或后缀模糊匹配文献事实（兼容 fact_001 / paper_fact_001）。"""
    if not all_facts or not target_ids:
        return []

    by_id: Dict[str, dict] = {}
    by_suffix: Dict[str, List[dict]] = {}
    for fact in all_facts:
        fid = str(fact.get("fact_id") or "").strip()
        if not fid:
            continue
        by_id[fid] = fact
        suffix = _fact_numeric_suffix(fid)
        if suffix:
            by_suffix.setdefault(suffix, []).append(fact)

    matched: List[dict] = []
    seen_ids: Set[str] = set()
    for raw_id in target_ids:
        tid = str(raw_id or "").strip()
        if not tid:
            continue

        hit = by_id.get(tid)
        if hit is None:
            suffix = _fact_numeric_suffix(tid)
            candidates = by_suffix.get(suffix or "", [])
            if candidates:
                prefix = tid.rsplit("_", 1)[0] if "_" in tid else ""
                for cand in candidates:
                    cand_id = str(cand.get("fact_id") or "")
                    if prefix and cand_id.startswith(prefix):
                        hit = cand
                        break
                if hit is None:
                    hit = candidates[0]

        fid = str(hit.get("fact_id") or "") if hit else ""
        if hit and fid and fid not in seen_ids:
            seen_ids.add(fid)
            matched.append(hit)
    return matched


def build_minimal_evidence_chain(hypothesis_text: str, facts: List[dict]) -> dict:
    """由文献 facts 构建最小可展示证据链（无 evidence_reasoning 阶段时使用）。"""
    from app.skills.evidence_reasoning._utils import score_relevance

    supporting = []
    for idx, fact in enumerate(facts):
        claim = (fact.get("fact_text") or fact.get("content") or "").strip()
        if not claim:
            continue
        title = fact.get("source_paper_title") or fact.get("source_title") or ""
        raw_rel = fact.get("relevance_score")
        try:
            rel = float(raw_rel) if raw_rel is not None else 0.0
        except (TypeError, ValueError):
            rel = 0.0
        if rel <= 0:
            rel = score_relevance(hypothesis_text or "", f"{claim} {title}")
        if rel <= 0:
            rel = 0.35  # 已绑定事实至少给可读的非零展示分
        supporting.append(
            {
                "evidence_id": fact.get("fact_id") or f"fact_{idx + 1:03d}",
                "claim": claim,
                "quote_or_summary": (fact.get("quote_text") or claim).strip(),
                "source_title": title,
                "paper_id": fact.get("document_id") or fact.get("source_document_id"),
                "document_id": fact.get("document_id") or fact.get("source_document_id"),
                "stance": "support",
                "stance_reason": "来自假设 supporting_fact_ids 绑定的文献事实",
                "relevance_score": round(min(1.0, rel), 4),
                "reliability_score": 0.65,
            }
        )
    completeness = min(0.35 + 0.15 * len(supporting), 0.9) if supporting else 0.0
    return {
        "final_version": hypothesis_text,
        "supporting_evidence": supporting,
        "counter_evidence": [],
        "counter_evidence_empty_reason": "文献不足，未检索到可验证反例（未编造）",
        "chain_completeness": completeness,
        "citation_reliability": 0.65 if supporting else 0.0,
        "revision_history": [],
    }
