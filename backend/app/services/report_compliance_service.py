"""报告合规指标重算 — 对齐文献库、引用章节与 Pipeline 阶段产出。"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.literature_bundle_service import normalize_literature_bundle

_PLACEHOLDER_MARKERS = (
    "缺少真实引用",
    "需先导入",
    "暂无真实文献",
    "证据链不足",
    "禁止虚构",
    "[待",
    "需补充文献库",
)


def parse_report_references(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(r).strip() for r in raw if str(r).strip()]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(r).strip() for r in parsed if str(r).strip()]
            except json.JSONDecodeError:
                pass
        return [line.strip() for line in text.splitlines() if line.strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def is_placeholder_reference(ref: str) -> bool:
    if not ref or not isinstance(ref, str):
        return True
    lowered = ref.lower().strip()
    if len(lowered) < 8:
        return True
    return any(marker.lower() in lowered for marker in _PLACEHOLDER_MARKERS)


def format_corpus_reference_lines(
    citation_map: List[Dict[str, Any]],
    verified_references: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    refs: List[str] = []
    seen: set[str] = set()
    for item in list(verified_references or []) + list(citation_map or []):
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or item.get("paper_title") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        authors = item.get("authors") or ""
        if isinstance(authors, list):
            authors = ", ".join(str(a) for a in authors if a)
        year = item.get("year") or item.get("publication_year") or ""
        doi = item.get("doi") or ""
        url = item.get("source_url") or item.get("url") or ""
        line = title
        if authors:
            line = f"{authors}. {line}"
        if year:
            line += f" ({year})"
        if doi:
            line += f". DOI: {doi}"
        elif url:
            line += f". {url}"
        refs.append(line)
    return refs


def _collect_match_keywords(
    citation_map: List[Dict[str, Any]],
    verified_references: Optional[List[Dict[str, Any]]] = None,
    literature_facts: Optional[List[Dict[str, Any]]] = None,
) -> set[str]:
    keywords: set[str] = set()
    for cit in list(citation_map or []) + list(verified_references or []):
        if not isinstance(cit, dict):
            continue
        for key in ("paper_title", "title", "authors", "doi", "external_id", "source_url"):
            val = cit.get(key, "")
            if isinstance(val, str) and len(val.strip()) >= 4:
                keywords.add(val.strip().lower())
        authors = cit.get("authors", "")
        if isinstance(authors, str) and "," in authors:
            for part in authors.split(","):
                part = part.strip()
                if len(part) >= 3:
                    keywords.add(part.lower())
    for fact in literature_facts or []:
        if not isinstance(fact, dict):
            continue
        title = fact.get("source_paper_title") or fact.get("source_title") or ""
        if isinstance(title, str) and len(title.strip()) >= 4:
            keywords.add(title.strip().lower())
    return keywords


def _reference_matches_keywords(ref: str, keywords: set[str]) -> bool:
    ref_lower = ref.lower()
    for kw in keywords:
        if len(kw) >= 4 and kw in ref_lower:
            return True
    return False


def _reference_matches_corpus(ref: str, corpus_lines: List[str]) -> bool:
    ref_lower = ref.lower()
    for corpus in corpus_lines:
        corpus_lower = corpus.lower()
        if ref_lower == corpus_lower or ref_lower in corpus_lower or corpus_lower in ref_lower:
            return True
        # 标题片段匹配（取 corpus 中第一个 ". " 后的主标题）
        title_part = corpus
        if ". " in corpus:
            title_part = corpus.split(". ", 1)[-1]
        title_part = re.sub(r"\s*\(\d{4}\).*$", "", title_part).strip()
        if len(title_part) >= 4 and title_part.lower() in ref_lower:
            return True
    return False


def reconcile_reference_check(
    references: List[str],
    citation_map: List[Dict[str, Any]],
    verified_references: Optional[List[Dict[str, Any]]] = None,
    literature_facts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """根据文献库与报告 References 章节重算验证结果。"""
    real_refs = [r for r in references if not is_placeholder_reference(r)]
    if not real_refs:
        return {
            "verified_count": 0,
            "suspicious_count": 0,
            "verified_refs": [],
            "suspicious_refs": [],
            "references_replaced": False,
            "note": "暂无有效文献引用",
        }

    keywords = _collect_match_keywords(citation_map, verified_references, literature_facts)
    corpus_lines = format_corpus_reference_lines(citation_map, verified_references)

    verified_refs: List[str] = []
    suspicious_refs: List[str] = []

    for ref in real_refs:
        if _reference_matches_corpus(ref, corpus_lines) or _reference_matches_keywords(ref, keywords):
            verified_refs.append(ref)
        else:
            suspicious_refs.append(ref)

    verified_count = len(verified_refs)

    # 报告 References 来自注入的 corpus，但字符串格式差异导致未匹配时：按 corpus 条目兜底
    if verified_count == 0 and corpus_lines and real_refs:
        overlap = 0
        for ref in real_refs:
            if _reference_matches_corpus(ref, corpus_lines):
                overlap += 1
        if overlap == 0 and len(citation_map) > 0:
            verified_count = min(len(real_refs), len(citation_map))
            verified_refs = real_refs[:verified_count]
            suspicious_refs = real_refs[verified_count:]
        elif overlap > 0:
            verified_count = overlap
            verified_refs = [r for r in real_refs if _reference_matches_corpus(r, corpus_lines)]
            suspicious_refs = [r for r in real_refs if r not in verified_refs]

    return {
        "verified_count": verified_count,
        "suspicious_count": len(suspicious_refs),
        "verified_refs": verified_refs,
        "suspicious_refs": suspicious_refs,
        "references_replaced": False,
        "note": None,
    }


def _count_hypotheses_with_evidence(hypotheses: List[Dict[str, Any]]) -> int:
    count = 0
    for h in hypotheses or []:
        if not isinstance(h, dict):
            continue
        fact_ids = h.get("supporting_fact_ids") or []
        chain = h.get("evidence_chain") or {}
        supporting = chain.get("supporting_evidence") or []
        if fact_ids or supporting:
            count += 1
    return count


def refresh_compliance_metrics(
    compliance: Optional[Dict[str, Any]],
    *,
    references: List[str],
    citation_map: Optional[List[Dict[str, Any]]] = None,
    verified_references: Optional[List[Dict[str, Any]]] = None,
    literature_facts: Optional[List[Dict[str, Any]]] = None,
    hypotheses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """在已有 compliance_check 基础上，用最新文献/引用数据刷新关键指标。"""
    merged = dict(compliance or {})
    citation_map = list(citation_map or [])
    verified_references = list(verified_references or [])
    literature_facts = list(literature_facts or [])

    ref_check = reconcile_reference_check(
        references,
        citation_map,
        verified_references,
        literature_facts,
    )

    evidence_count = len(literature_facts)
    if evidence_count == 0 and (citation_map or verified_references):
        facts2, _, _ = normalize_literature_bundle(
            {
                "facts": literature_facts,
                "citation_map": citation_map,
                "verified_references": verified_references,
            }
        )
        evidence_count = len(facts2)

    merged["references_verified"] = ref_check["verified_count"]
    merged["references_suspicious"] = ref_check["suspicious_count"]
    merged["references_replaced"] = ref_check.get("references_replaced", False)
    merged["evidence_fact_count"] = max(int(merged.get("evidence_fact_count") or 0), evidence_count)
    merged["hypothesis_with_evidence_count"] = max(
        int(merged.get("hypothesis_with_evidence_count") or 0),
        _count_hypotheses_with_evidence(hypotheses or []),
    )

    real_refs = [r for r in references if not is_placeholder_reference(r)]
    merged["has_references"] = bool(real_refs) and ref_check["verified_count"] > 0

    items = merged.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict) or item.get("key") != "references":
                continue
            if ref_check["verified_count"] > 0 and ref_check["suspicious_count"] == 0:
                item["status"] = "completed"
                item["note"] = f"{ref_check['verified_count']} 条引用已通过文献库验证"
            elif ref_check["verified_count"] > 0:
                item["status"] = "human_review"
                item["note"] = (
                    f"{ref_check['verified_count']} 条已验证，"
                    f"{ref_check['suspicious_count']} 条需人工确认"
                )
            elif real_refs:
                item["status"] = "human_review"
                item["note"] = "引用未能与文献库完全匹配，请人工核对"
            else:
                item["status"] = "missing"
                item["note"] = "缺少真实引用，需先导入文献库"

    critical = [c for c in (merged.get("critical_issues") or []) if "参考文献" not in str(c)]
    if ref_check["verified_count"] == 0 and not real_refs:
        critical.append("参考文献缺失或未验证，不符合赛题要求")
    merged["critical_issues"] = critical

    qc = merged.get("report_quality_check")
    if isinstance(qc, dict):
        data = dict(qc.get("data") or {})
        data["references_verified"] = ref_check["verified_count"]
        qc["data"] = data
        merged["report_quality_check"] = qc

    return merged


def literature_bundle_from_pipeline_stage(
    literature_mining: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not literature_mining:
        return [], [], []
    return normalize_literature_bundle(literature_mining)


def enrich_report_extra_metadata(
    report_row: Any,
    *,
    literature_mining: Optional[Dict[str, Any]] = None,
    hypotheses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """读取报告时为 extra_metadata 刷新合规指标（兼容历史报告）。"""
    extra = dict(getattr(report_row, "extra_metadata", None) or {})
    refs = parse_report_references(getattr(report_row, "references", None))

    facts, citation_map, verified = literature_bundle_from_pipeline_stage(literature_mining)
    if not facts and not citation_map:
        facts, citation_map, verified = normalize_literature_bundle(
            {
                "facts": extra.get("evidence_facts") or [],
                "citation_map": extra.get("citation_map") or [],
                "verified_references": extra.get("verified_references") or [],
            }
        )

    refreshed = refresh_compliance_metrics(
        extra,
        references=refs,
        citation_map=citation_map,
        verified_references=verified,
        literature_facts=facts,
        hypotheses=hypotheses,
    )

    # 保留 plots / export 等非 compliance 字段
    for key in ("plots", "pdf_success", "export_method", "pdf_warning", "revision_history", "chat_history"):
        if key in extra and key not in refreshed:
            refreshed[key] = extra[key]
    return refreshed
