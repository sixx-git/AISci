"""
自动评分模块（三套生成器共用）— 对照评分表逐条评估报告。

v3 改进:
  - 分数归一化与 clamp（0 / weight/2 / weight）
  - 批失败降级为单条重试、漏项补评
  - 可选源文献上下文（--source-dir）
  - 长报告智能截断
  - 按 task_type 特化 prompt
  - scoring_meta 与批级 checkpoint
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_MAX_REPORT_CHARS = 200000
# 论文全文评估时使用更大的上限，避免截断导致评分项找不到证据
DEFAULT_PAPER_MAX_REPORT_CHARS = 200000
DEFAULT_BATCH_SIZE = 10
DEFAULT_SOURCE_EXCERPT_CHARS = 800
SINGLE_RETRY_ATTEMPTS = 2

# 长报告截断：保留首尾 + 关键章节
HEAD_RATIO = 0.35
TAIL_RATIO = 0.25
SECTION_PATTERNS = [
    # Markdown 标题格式（报告类）
    r"(?im)^#{1,4}\s*abstract\b.*?(?=^#{1,4}\s|\Z)",
    r"(?im)^#{1,4}\s*conclusion\b.*?(?=^#{1,4}\s|\Z)",
    r"(?im)^#{1,4}\s*verdict\b.*?(?=^#{1,4}\s|\Z)",
    r"(?im)^#{1,4}\s*summary\b.*?(?=^#{1,4}\s|\Z)",
    r"(?im)^#{1,4}\s*discussion\b.*?(?=^#{1,4}\s|\Z)",
    r"(?im)^#{1,4}\s*future\s+directions?\b.*?(?=^#{1,4}\s|\Z)",
    # 纯文本论文格式（PDF提取后的文本，标题通常是全大写或首字母大写独占一行）
    r"(?im)^(?:\s*\n)?(abstract)\s*\n.*?(?=\n\s*(?:introduction|1[\.\s]|\d+\.\s+[A-Z]|\Z))",
    r"(?im)^(?:\s*\n)?(introduction)\s*\n.*?(?=\n\s*(?:methods?|2[\.\s]|\d+\.\s+[A-Z]|\Z))",
    r"(?im)^(?:\s*\n)?(methods?|methodology|materials?\s+and\s+methods?)\s*\n.*?(?=\n\s*(?:results?|3[\.\s]|\d+\.\s+[A-Z]|\Z))",
    r"(?im)^(?:\s*\n)?(results?|findings?)\s*\n.*?(?=\n\s*(?:discussion|conclusion|4[\.\s]|\d+\.\s+[A-Z]|\Z))",
    r"(?im)^(?:\s*\n)?(discussion)\s*\n.*?(?=\n\s*(?:conclusion|5[\.\s]|\d+\.\s+[A-Z]|\Z))",
    r"(?im)^(?:\s*\n)?(conclusions?)\s*\n.*?(?=\n\s*(?:references?|acknowledg|6[\.\s]|\d+\.\s+[A-Z]|\Z))",
    # 数字编号章节（如 "1. Introduction", "2. Methods"）
    r"(?im)^\d+[\.\)]\s*(?:introduction|methods?|results?|discussion|conclusion|abstract)\b.*?(?=^\d+[\.\)]\s*[A-Z]|\Z)",
]

from common.rubric_observability import (
    format_elements_for_prompt,
    score_from_checklist,
)

TASK_TYPE_GUIDANCE = {
    "claim_verification": (
        "**Task focus (claim verification)**: Evaluate whether the report builds a "
        "clear claim-analysis chain, synthesizes cross-source evidence, states boundary "
        "conditions, and provides an explicit Verdict with an evidence table mapping "
        "sub-propositions to sources."
    ),
    "data_analysis": (
        "**Task focus (data analysis)**: Evaluate whether the report correctly interprets "
        "experimental data, applies appropriate statistical reasoning, compares algorithms "
        "or conditions rigorously, and ties conclusions back to data constraints and "
        "experimental design."
    ),
    "literature_review": (
        "**Task focus (literature review)**: Evaluate whether the report provides coherent "
        "taxonomy, temporal coverage, cross-method comparison, bottleneck analysis, and "
        "forward-looking research directions grounded in the cited literature."
    ),
}

PROMPT_SCORE_BATCH = """\
You are a strict academic report evaluator. Evaluate the given report against each rubric item below.

{task_type_guidance}

**Rubric Items** ({count} items in this batch):
{rubric_items_text}
{shared_source_context}

**Report to Evaluate**:
---
{report_text}
---

**Scoring Rules**:
- **judgment_mode=binary**: Score ONLY 0 or full weight (no half credit). Full credit requires explicit report evidence for the verifiable proposition.
- **judgment_mode=checklist**: List which required elements (A, B, C...) are clearly supported. Score by element count (see each item). Return `matched_elements` as letter labels.
- **judgment_mode=structure**: Standard 0 / half / full rules for structural items.
- Do NOT use subjective judgment like "adequately" or "sufficiently explains" — only check presence of required observable content.

**Important**:
1. Evaluate EVERY item. Do not skip any.
2. The "reason" must cite specific content from the report as evidence.
3. Be strict and objective. Do not give partial credit unless the report genuinely attempts to address the item.
4. If source_ids is "none", evaluate report structure/content only — do NOT require specific source citations.
5. If source_ids lists sources, check whether the report's claims align with what those sources support (when source excerpts are provided).
6. Consider the item's ROLE: Critical items require the highest standard; Mandatory require clear evidence; Standard require substantive mention.

Output as JSON array:
[
  {{
    "rubric_id": "R1",
    "score": 4,
    "matched_elements": ["A", "B"],
    "reason": "The report explicitly states in Section X that..."
  }}
]

Output JSON only, no other text.
"""

PROMPT_SCORE_SINGLE = """\
You are a strict academic report evaluator. Evaluate whether the report satisfies the following rubric item.

{task_type_guidance}

**Rubric Item**:
- ID: {rubric_id}
- Question: {question}
- Max Score: {weight}
- Role: {role}
- Source References: {source_ids}
{source_excerpt}

**Report to Evaluate**:
---
{report_text}
---

Scoring:
- Full score ({weight}): The report explicitly and thoroughly addresses the item.
- Half score ({half}): Partial coverage or mention without depth.
- Zero (0): Completely missing.

If source_ids is "none", evaluate report quality only without requiring citations.

Output as JSON:
{{
  "rubric_id": "{rubric_id}",
  "score": <number>,
  "reason": "<detailed reason citing specific report content>"
}}

Output JSON only, no other text.
"""


def normalize_item_score(item: Optional[dict], row: dict) -> Tuple[float, List[str], List[str]]:
    """按 judgment_mode 归一化单项得分。返回 (score, warnings, matched_elements)。"""
    weight = int(item.get("weight", 1)) if item else 1
    mode = (item or {}).get("judgment_mode", "binary")
    warnings: List[str] = []
    matched = row.get("matched_elements") or []
    if not isinstance(matched, list):
        matched = []

    if mode == "checklist" and item and item.get("required_elements"):
        elems = item.get("required_elements") or []
        if matched:
            count = len(matched)
        else:
            count = len(matched) if matched else 0
            raw = row.get("score", 0)
            try:
                mf = int(item.get("min_elements_full", 2))
                mh = int(item.get("min_elements_half", 1))
                full_score = float(weight)
                half_score = float(weight) / 2.0
                rv = float(raw)
                if rv >= full_score * 0.9:
                    count = mf
                elif rv >= half_score * 0.9:
                    count = mh
                else:
                    count = 0
            except (TypeError, ValueError):
                count = 0
        score = score_from_checklist(
            count,
            weight,
            int(item.get("min_elements_full", 2)),
            int(item.get("min_elements_half", 1)),
        )
        return score, warnings, matched

    score, warns = normalize_score(row.get("score", 0), weight)
    warnings.extend(warns)
    if mode == "binary" and 0 < score < weight:
        score = float(weight) if score >= weight / 2.0 else 0.0
        warnings.append("binary_mode_no_half_credit")
    return score, warnings, matched


def normalize_score(raw: Any, weight: int) -> Tuple[float, List[str]]:
    """将 LLM 分数归一化到 {0, weight/2, weight}。"""
    warnings: List[str] = []
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 0.0, ["invalid_score_type"]

    if weight <= 0:
        return 0.0, ["invalid_weight"]

    half = weight / 2.0
    allowed = [0.0, half, float(weight)]

    if val < 0:
        warnings.append("score_clamped_below_zero")
        val = 0.0
    elif val > weight:
        warnings.append("score_clamped_above_max")
        val = float(weight)

    nearest = min(allowed, key=lambda a: abs(a - val))
    if abs(nearest - val) > 0.01:
        warnings.append(f"score_snapped_{val}_to_{nearest}")
    return nearest, warnings


def prepare_report_text(text: str, max_chars: int = DEFAULT_MAX_REPORT_CHARS) -> Tuple[str, Dict[str, Any]]:
    """智能截断长报告：保留开头、结尾与关键章节。"""
    meta: Dict[str, Any] = {
        "truncated": False,
        "original_chars": len(text),
        "used_chars": len(text),
        "max_chars": max_chars,
    }
    if len(text) <= max_chars:
        return text, meta

    meta["truncated"] = True
    head_size = int(max_chars * HEAD_RATIO)
    tail_size = int(max_chars * TAIL_RATIO)
    budget_for_sections = max(0, max_chars - head_size - tail_size - 200)

    sections: List[str] = []
    seen_spans: List[Tuple[int, int]] = []

    for pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.DOTALL):
            start, end = match.span()
            if any(not (end <= s or start >= e) for s, e in seen_spans):
                continue
            chunk = match.group(0).strip()
            if len(chunk) > 80:
                # 根据截断上限动态调整每个章节的保留长度
                # 旧值固定1200太小，改为 max_chars 的 8%，上限 5000
                chunk_max = min(5000, max(1200, int(max_chars * 0.08)))
                sections.append(chunk[:chunk_max])
                seen_spans.append((start, end))

    section_text = "\n\n---\n\n".join(sections)
    if len(section_text) > budget_for_sections:
        section_text = section_text[:budget_for_sections]

    parts = [text[:head_size]]
    if section_text:
        parts.append(
            f"\n\n... [Extracted key sections ({len(sections)} blocks)] ...\n\n{section_text}"
        )
    parts.append(f"\n\n... [Report tail preserved] ...\n\n{text[-tail_size:]}")

    result = "".join(parts)
    # 如果总长超过上限，逐步缩减非关键部分
    if len(result) > max_chars:
        # 优先策略：保留完整的关键章节，缩减头部和尾部
        # 先尝试只保留头部的一部分 + 完整章节 + 尾部的一部分
        shrink_head = int(max_chars * 0.30)
        shrink_tail = int(max_chars * 0.20)
        remaining = max_chars - shrink_head - shrink_tail - 100
        if len(section_text) > remaining:
            section_text = section_text[:remaining]
        parts = [
            text[:shrink_head],
            f"\n\n... [Extracted key sections ({len(sections)} blocks)] ...\n\n{section_text}" if section_text else "",
            f"\n\n... [Report tail preserved] ...\n\n{text[-shrink_tail:]}",
        ]
        result = "".join(p for p in parts if p)
        if len(result) > max_chars:
            result = result[:max_chars]
    result += "\n\n... [Report truncated for context window] ..."

    meta["used_chars"] = len(result)
    meta["sections_extracted"] = len(sections)
    return result, meta


def build_source_map(sources: Optional[List[Any]]) -> Dict[str, Any]:
    if not sources:
        return {}
    return {s.source_id: s for s in sources}


def build_source_excerpt(
    source_map: Dict[str, Any],
    source_ids: List[str],
    per_source_max: int = DEFAULT_SOURCE_EXCERPT_CHARS,
) -> str:
    if not source_ids or not source_map:
        return ""
    parts = []
    for sid in source_ids:
        doc = source_map.get(sid)
        if not doc:
            continue
        excerpt = doc.get_summary_for_llm(max_chars=per_source_max)
        parts.append(f"[{sid}: {doc.file_name}]\n{excerpt}")
    return "\n\n".join(parts)


def build_shared_source_context(
    source_map: Dict[str, Any],
    batch: List[dict],
    per_source_max: int = DEFAULT_SOURCE_EXCERPT_CHARS,
) -> str:
    """批内去重后的源文献摘要块。"""
    if not source_map:
        return ""
    ids: List[str] = []
    for it in batch:
        for sid in it.get("source_ids") or []:
            if sid and sid not in ids:
                ids.append(sid)
    excerpt = build_source_excerpt(source_map, ids, per_source_max)
    if not excerpt:
        return ""
    return f"\n**Source Document Excerpts (for reference)**:\n---\n{excerpt}\n---\n"


def relative_report_path(report_path: str, output_dir: Optional[str]) -> str:
    """尽量写入相对 output 的路径。"""
    rp = Path(report_path)
    if output_dir:
        try:
            return str(rp.relative_to(Path(output_dir).resolve()))
        except ValueError:
            pass
    try:
        return str(rp.relative_to(Path.cwd()))
    except ValueError:
        return str(rp)


def get_task_type_guidance(task_type: Optional[str]) -> str:
    if not task_type:
        return ""
    return TASK_TYPE_GUIDANCE.get(task_type, "")


def _safe_int(value: Any, default: int) -> int:
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


class Scorer:
    """自动评分器 v3（共用实现）。"""

    BATCH_SIZE = DEFAULT_BATCH_SIZE

    def __init__(self, config):
        self.config = config
        self.client = config.get_client()
        self.batch_size = _safe_int(
            getattr(config, "scoring_batch_size", None), DEFAULT_BATCH_SIZE
        )
        self.max_report_chars = _safe_int(
            getattr(config, "max_report_chars", None), DEFAULT_MAX_REPORT_CHARS
        )
        temp = getattr(config, "scoring_temperature", None)
        try:
            self.scoring_temperature = float(temp) if temp is not None else 0.1
        except (TypeError, ValueError):
            self.scoring_temperature = 0.1

    def score(
        self,
        report_path: str,
        rubric_data: Dict[str, Any],
        sources: Optional[List[Any]] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        report_text = self._load_report(report_path)
        if not report_text:
            raise ValueError(f"无法读取报告: {report_path}")

        if "rubrics" not in rubric_data or "dimensions" not in rubric_data["rubrics"]:
            raise ValueError("task.json 缺少 rubrics.dimensions 结构")

        logger.info(f"报告长度: {len(report_text)} 字符")

        all_items: List[dict] = []
        for dim in rubric_data["rubrics"]["dimensions"]:
            all_items.extend(dim["items"])

        task_type = rubric_data.get("task_type")
        task_guidance = get_task_type_guidance(task_type)
        source_map = build_source_map(sources)

        report_for_scoring, trunc_meta = prepare_report_text(
            report_text, self.max_report_chars
        )
        if trunc_meta.get("truncated"):
            logger.warning(
                f"报告已截断: {trunc_meta['original_chars']} -> {trunc_meta['used_chars']} 字符"
            )

        scoring_meta: Dict[str, Any] = {
            "scorer_version": "v3",
            "task_type": task_type,
            "truncation": trunc_meta,
            "batches": 0,
            "retried_items": [],
            "warnings": [],
            "source_context_used": bool(source_map),
        }

        logger.info(f"共 {len(all_items)} 条评分项，分批评估...")
        scored_items, batch_meta = self._score_batched(
            report_for_scoring,
            all_items,
            source_map,
            task_guidance,
            output_dir,
        )
        scoring_meta["batches"] = batch_meta["batches"]
        scoring_meta["retried_items"] = batch_meta["retried_items"]
        scoring_meta["warnings"].extend(batch_meta["warnings"])

        result = self._aggregate_scores(
            scored_items,
            rubric_data,
            report_path,
            output_dir,
            scoring_meta,
        )
        return result

    def _load_report(self, report_path: str) -> str:
        path = Path(report_path)
        if not path.exists():
            return ""

        if path.suffix.lower() == ".pdf":
            try:
                import fitz

                doc = fitz.open(str(path))
                text_parts = [page.get_text("text") for page in doc]
                doc.close()
                return "\n\n".join(text_parts)
            except ImportError:
                logger.warning("PyMuPDF 未安装，无法解析 PDF 报告")
                return ""

        for encoding in ("utf-8-sig", "utf-8"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")

    def _score_batched(
        self,
        report_text: str,
        items: List[dict],
        source_map: Dict[str, Any],
        task_guidance: str,
        output_dir: Optional[str],
    ) -> Tuple[List[dict], Dict[str, Any]]:
        scored_by_id: Dict[str, dict] = {}
        meta: Dict[str, Any] = {"batches": 0, "retried_items": [], "warnings": []}
        partial_path = None
        if output_dir:
            partial_path = Path(output_dir) / "rubric_scores.partial.json"

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(items) + self.batch_size - 1) // self.batch_size
            meta["batches"] = batch_num

            logger.info(
                f"  Evaluating batch {batch_num}/{total_batches} "
                f"(items {i + 1}-{i + len(batch)})..."
            )

            batch_results = self._score_batch(
                report_text, batch, source_map, task_guidance
            )
            merged, missing = self._merge_batch_results(batch, batch_results, meta)

            for rid in missing:
                logger.info(f"    补评漏项: {rid}")
                item = next(it for it in batch if it["rubric_id"] == rid)
                single = self._score_single_with_retry(
                    report_text, item, source_map, task_guidance
                )
                merged[rid] = single
                meta["retried_items"].append(rid)

            scored_by_id.update(merged)

            if partial_path is not None:
                self._write_partial_checkpoint(
                    partial_path, list(scored_by_id.values()), batch_num, total_batches
                )

        ordered = []
        for it in items:
            rid = it["rubric_id"]
            ordered.append(
                scored_by_id.get(
                    rid,
                    {
                        "rubric_id": rid,
                        "score": 0,
                        "reason": "Not scored",
                        "normalization_warnings": ["missing_final"],
                    },
                )
            )
        return ordered, meta

    def _score_batch(
        self,
        report_text: str,
        batch: List[dict],
        source_map: Dict[str, Any],
        task_guidance: str,
    ) -> List[dict]:
        items_text = "\n".join(
            self._fmt_item(it, source_map) for it in batch
        )
        shared_ctx = build_shared_source_context(source_map, batch)

        prompt = PROMPT_SCORE_BATCH.format(
            task_type_guidance=task_guidance,
            count=len(batch),
            rubric_items_text=items_text,
            shared_source_context=shared_ctx,
            report_text=report_text,
        )

        try:
            results = self._call_llm_json(
                prompt,
                system=(
                    "You are a strict academic report evaluator. "
                    "Score every item rigorously. Output JSON only."
                ),
            )
            if isinstance(results, list) and results:
                normalized = []
                for row in results:
                    if not isinstance(row, dict) or "rubric_id" not in row:
                        continue
                    item = next(
                        (it for it in batch if it["rubric_id"] == row["rubric_id"]),
                        None,
                    )
                    weight = item["weight"] if item else 1
                    score, warns, matched = normalize_item_score(item, row)
                    entry = {
                        "rubric_id": row["rubric_id"],
                        "score": score,
                        "reason": row.get("reason", ""),
                        "normalization_warnings": warns,
                    }
                    if matched:
                        entry["matched_elements"] = matched
                    normalized.append(entry)
                if normalized:
                    return normalized
        except Exception as e:
            logger.error(f"Batch scoring failed: {e}")

        logger.warning("批评分失败，降级为单条评分")
        fallback = []
        for it in batch:
            fallback.append(
                self._score_single_with_retry(
                    report_text, it, source_map, task_guidance
                )
            )
        return fallback

    def _score_single_with_retry(
        self,
        report_text: str,
        item: dict,
        source_map: Dict[str, Any],
        task_guidance: str,
    ) -> dict:
        last_error = None
        for attempt in range(SINGLE_RETRY_ATTEMPTS):
            try:
                result = self._score_single(
                    report_text, item, source_map, task_guidance
                )
                if result.get("reason") != "Scoring failed":
                    return result
            except Exception as e:
                last_error = e
                logger.warning(
                    f"单条评分 {item['rubric_id']} 失败 (尝试 {attempt + 1}): {e}"
                )
        return {
            "rubric_id": item["rubric_id"],
            "score": 0,
            "reason": f"Scoring failed: {last_error}" if last_error else "Scoring failed",
            "normalization_warnings": ["single_retry_exhausted"],
        }

    def _score_single(
        self,
        report_text: str,
        item: dict,
        source_map: Dict[str, Any],
        task_guidance: str,
    ) -> dict:
        sids = ", ".join(item.get("source_ids") or []) or "none"
        excerpt = build_source_excerpt(source_map, item.get("source_ids") or [])
        source_block = f"\n**Source Excerpts**:\n{excerpt}\n" if excerpt else ""
        half = item["weight"] / 2

        prompt = PROMPT_SCORE_SINGLE.format(
            task_type_guidance=task_guidance,
            rubric_id=item["rubric_id"],
            question=item["question"],
            weight=item["weight"],
            role=item.get("role", "Standard"),
            source_ids=sids,
            source_excerpt=source_block,
            report_text=report_text,
            half=half,
        )

        result = self._call_llm_json(
            prompt,
            system="You are a strict academic report evaluator. Output JSON only.",
        )
        if isinstance(result, dict) and result.get("rubric_id"):
            score, warns, matched = normalize_item_score(item, result)
            entry = {
                "rubric_id": item["rubric_id"],
                "score": score,
                "reason": result.get("reason", ""),
                "normalization_warnings": warns,
            }
            if matched:
                entry["matched_elements"] = matched
            return entry
        raise ValueError(f"Invalid single score response for {item['rubric_id']}")

    def _merge_batch_results(
        self,
        batch: List[dict],
        results: List[dict],
        meta: Dict[str, Any],
    ) -> Tuple[Dict[str, dict], List[str]]:
        by_id: Dict[str, dict] = {}
        duplicate_ids: List[str] = []

        for row in results:
            rid = row.get("rubric_id")
            if not rid:
                meta["warnings"].append("batch_result_missing_rubric_id")
                continue
            if rid in by_id:
                duplicate_ids.append(rid)
                meta["warnings"].append(f"duplicate_rubric_id_{rid}")
            by_id[rid] = row

        if duplicate_ids:
            logger.warning(f"批结果重复 rubric_id: {duplicate_ids}")

        expected = {it["rubric_id"] for it in batch}
        missing = sorted(expected - set(by_id.keys()))
        if missing:
            meta["warnings"].append(f"batch_missing_items:{','.join(missing)}")
        return by_id, missing

    def _fmt_item(self, it: dict, source_map: Dict[str, Any]) -> str:
        role = it.get("role", "Standard")
        cat = it.get("competency_category", "")
        q = it["question"]
        sids = ", ".join(it.get("source_ids") or []) or "none"
        mode = it.get("judgment_mode", "binary")
        elems = it.get("required_elements") or []
        note = ""
        if sids == "none":
            note = " [evaluate report only, no citation required]"
        elem_block = ""
        if elems:
            elem_block = (
                f"\n    Required elements ({mode}, "
                f"full>={it.get('min_elements_full', 2)}, "
                f"half>={it.get('min_elements_half', 1)}):\n"
                + format_elements_for_prompt(elems)
            )
        return (
            f"  {it['rubric_id']} (max {it['weight']} pts, role={role}, "
            f"cat={cat}, mode={mode}, sources: {sids}){note}: {q}"
            f"{elem_block}"
        )

    def _aggregate_scores(
        self,
        scored_items: List[dict],
        rubric_data: dict,
        report_path: str,
        output_dir: Optional[str],
        scoring_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        score_map = {item["rubric_id"]: item for item in scored_items}

        dimension_scores = []
        total_raw = 0.0
        total_max = 0
        weight_map: Dict[str, int] = {}

        for dim in rubric_data["rubrics"]["dimensions"]:
            for item in dim["items"]:
                weight_map[item["rubric_id"]] = item["weight"]

        for dim in rubric_data["rubrics"]["dimensions"]:
            dim_raw = 0.0
            dim_max = dim["max_score"]
            dim_weight_sum = sum(it["weight"] for it in dim["items"])

            if dim_weight_sum != dim_max:
                scoring_meta["warnings"].append(
                    f"dimension_max_mismatch:{dim['dimension_id']}"
                )

            for item in dim["items"]:
                rid = item["rubric_id"]
                scored = score_map.get(
                    rid, {"score": 0, "reason": "Not scored"}
                )
                dim_raw += float(scored.get("score", 0))

            dimension_scores.append({
                "dimension_id": dim["dimension_id"],
                "score": round(dim_raw, 2),
                "max_score": dim_max,
            })
            total_raw += dim_raw
            total_max += dim_max

        total_raw = round(total_raw, 2)
        if total_raw > total_max:
            scoring_meta["warnings"].append(
                f"raw_score_exceeds_total:{total_raw}>{total_max}"
            )
            logger.warning(
                f"原始分 {total_raw} 超过满分 {total_max}，已截断至满分"
            )
            total_raw = float(total_max)

        items_out = []
        full_mark_count = 0
        zero_count = 0
        for dim in rubric_data["rubrics"]["dimensions"]:
            for item in dim["items"]:
                rid = item["rubric_id"]
                scored = score_map.get(rid, {"score": 0, "reason": "Not scored"})
                score_val = float(scored.get("score", 0))
                weight = weight_map[rid]
                if score_val <= 0:
                    zero_count += 1
                if score_val >= weight:
                    full_mark_count += 1
                entry = {
                    "rubric_id": rid,
                    "score": score_val,
                    "reason": scored.get("reason", ""),
                }
                norm_warns = scored.get("normalization_warnings")
                if norm_warns:
                    entry["normalization_warnings"] = norm_warns
                items_out.append(entry)

        scoring_meta["zero_count"] = zero_count
        scoring_meta["full_mark_count"] = full_mark_count

        partial_path = Path(output_dir) / "rubric_scores.partial.json" if output_dir else None
        if partial_path and partial_path.exists():
            try:
                partial_path.unlink()
            except OSError:
                pass

        return {
            "model_name": self.config.scoring_model,
            "report_file": relative_report_path(report_path, output_dir),
            "raw_score": total_raw,
            "total_score": total_max,
            "score_percentage": round(total_raw / total_max * 100, 2) if total_max > 0 else 0,
            "dimension_scores": dimension_scores,
            "items": items_out,
            "scoring_meta": scoring_meta,
        }

    def _write_partial_checkpoint(
        self,
        path: Path,
        scored_items: List[dict],
        batch_num: int,
        total_batches: int,
    ) -> None:
        payload = {
            "checkpoint": True,
            "batch_completed": batch_num,
            "total_batches": total_batches,
            "items_scored": len(scored_items),
            "items": scored_items,
        }
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning(f"无法写入 checkpoint: {e}")

    def _call_llm_json(self, prompt: str, system: str = "") -> Any:
        from pipeline.llm_utils import call_llm_json

        return call_llm_json(
            self.client,
            self.config.scoring_model,
            prompt,
            system=system,
            temperature=self.scoring_temperature,
            max_retries=self.config.max_retries,
        )


def apply_scoring_options(config: Any, args: Any) -> None:
    """从 CLI args 写入评分相关配置（不影响生成逻辑）。"""
    max_chars = getattr(args, "max_report_chars", 0) or 0
    if max_chars > 0:
        config.max_report_chars = max_chars
    batch_size = getattr(args, "scoring_batch_size", 0) or 0
    if batch_size > 0:
        config.scoring_batch_size = batch_size


def add_scoring_arguments(parser, *, include_source_dir: bool = True) -> None:
    """为 score / full 子命令添加共用评分参数。"""
    if include_source_dir:
        parser.add_argument(
            "--source-dir",
            default="",
            help="源文件目录（可选，用于注入源文献上下文辅助评分）",
        )
    parser.add_argument(
        "--max-report-chars",
        type=int,
        default=0,
        help=f"报告截断上限（默认 {DEFAULT_MAX_REPORT_CHARS}）",
    )


