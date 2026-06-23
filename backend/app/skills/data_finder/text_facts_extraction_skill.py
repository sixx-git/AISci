"""正文轻量事实抽取 L1 — Methods/Results 中与 DataSpec 相关的数值句"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id

SECTION_PATTERNS = [
    (re.compile(r"\bmethods?\b", re.I), "methods"),
    (re.compile(r"\bresults?\b", re.I), "results"),
    (re.compile(r"\b实验方法\b"), "methods"),
    (re.compile(r"\b结果\b"), "results"),
]

NUMERIC_SENTENCE = re.compile(
    r"[^.!?。；\n]{5,200}?(?:\d+\.?\d*\s*%|\d+\.?\d*)[^.!?。；\n]{0,80}[.!?。]",
    re.I,
)

TABLE_REF = re.compile(r"(?:table|表)\s*(\d+[a-z]?)", re.I)


class TextFactsExtractionSkill(BaseSkill):
    name = "TextFactsExtraction"
    description = "从正文 Methods/Results 抽取与目标变量相关的数值句（L1，不进 merge）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        documents = input_data.get("documents") or []
        data_spec = input_data.get("data_spec") or {}
        targets = list(input_data.get("target_variables") or data_spec.get("target_variables") or [])
        max_facts = int(input_data.get("max_facts") or 20)

        target_tokens = self._expand_targets(targets)
        facts: List[Dict[str, Any]] = []

        for doc in documents:
            text = (doc.get("raw_text") or doc.get("abstract") or "").strip()
            if len(text) < 80:
                continue
            sections = self._split_sections(text)
            for section_name, section_text in sections.items():
                for sent in self._extract_numeric_sentences(section_text):
                    matched = self._match_targets(sent, target_tokens, targets)
                    if targets and not matched:
                        continue
                    numbers = re.findall(r"\d+\.?\d*", sent)
                    table_ref = self._table_ref(sent)
                    facts.append({
                        "fact_id": new_id("txtf"),
                        "paper_id": doc.get("id") or doc.get("document_id", ""),
                        "source_title": doc.get("title") or doc.get("filename", ""),
                        "section": section_name,
                        "sentence": sent.strip()[:400],
                        "matched_targets": matched,
                        "numeric_values": numbers[:6],
                        "table_ref": table_ref,
                        "extraction_tier": "L1_text_fact",
                        "extraction_method": "regex_section",
                        "confidence": 0.55 if matched else 0.45,
                    })
                    if len(facts) >= max_facts:
                        break
                if len(facts) >= max_facts:
                    break
            if len(facts) >= max_facts:
                break

        result.data = {"text_facts": facts[:max_facts], "count": len(facts[:max_facts])}
        if not facts and targets:
            result.add_warning("未在 Methods/Results 中命中与目标变量相关的数值句")
        return result

    @staticmethod
    def _expand_targets(targets: List[str]) -> Set[str]:
        tokens: Set[str] = set()
        for t in targets:
            t = str(t).strip().lower()
            if not t:
                continue
            tokens.add(t)
            tokens.add(t.replace("_", " "))
            for part in re.split(r"[_\s/]+", t):
                if len(part) >= 3:
                    tokens.add(part)
        return tokens

    @staticmethod
    def _split_sections(text: str) -> Dict[str, str]:
        lower = text.lower()
        bounds: List[tuple[int, str]] = []
        for pattern, name in SECTION_PATTERNS:
            for m in pattern.finditer(lower):
                bounds.append((m.start(), name))
        bounds.sort(key=lambda x: x[0])

        if not bounds:
            return {"body": text[:12000]}

        sections: Dict[str, str] = {}
        for i, (start, name) in enumerate(bounds):
            end = bounds[i + 1][0] if i + 1 < len(bounds) else len(text)
            chunk = text[start:end]
            sections[name] = sections.get(name, "") + "\n" + chunk
        return {k: v[:8000] for k, v in sections.items()}

    @staticmethod
    def _extract_numeric_sentences(section_text: str) -> List[str]:
        found = NUMERIC_SENTENCE.findall(section_text)
        if found:
            return found[:15]
        # 降级：按句号切分含数字的句
        sents = re.split(r"(?<=[.!?。])\s+", section_text)
        return [s for s in sents if re.search(r"\d", s)][:12]

    @staticmethod
    def _match_targets(sentence: str, tokens: Set[str], targets: List[str]) -> List[str]:
        if not targets:
            return []
        sl = sentence.lower()
        hit: List[str] = []
        for t in targets:
            tl = str(t).lower()
            if tl in sl or tl.replace("_", " ") in sl:
                hit.append(str(t))
            elif any(tok in sl for tok in tokens if tok in tl or tl in tok):
                if str(t) not in hit:
                    hit.append(str(t))
        return hit[:5]

    @staticmethod
    def _table_ref(sentence: str) -> str:
        m = TABLE_REF.search(sentence)
        return m.group(1) if m else ""
