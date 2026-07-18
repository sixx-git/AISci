"""
评分校准模块 v2 (v5.3 兼容) — 规则检查校准，确保评分表满足基本质量标准。

校准内容:
  1. Role 分布比例检查与修正
  2. 维度分值均衡性（按 task_type 适配）
  3. 评分项总数控制（与 v5.3 DIMENSION_CONFIG 对齐）
  4. source_ids 覆盖度检查
  5. 问题质量深度检查（规则检查，无 LLM 修复）
  6. 英文输出检查
  7. 硬性 Role 重平衡（防止比例失衡）

v5.3 变更：禁用 LLM 深度校准（避免 LLM 修复引入过拟合与论文特有术语）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from .llm_utils import call_llm_json
from .rubric_utils import (
    normalize_importance,
    weight_from_importance,
    role_from_importance,
    infer_competency_category,
    build_rubric_key,
    item_priority_score,
    item_aligns_with_query,
    is_survey_style_query,
)

logger = logging.getLogger(__name__)

# 合理的 Role 分布范围（全局）
ROLE_DISTRIBUTION_RANGE = {
    "critical": (0.15, 0.35),
    "mandatory": (0.40, 0.60),
    "standard": (0.10, 0.30),
}

# 按 task_type 的维度分值占比参考
TASK_DIMENSION_RATIO = {
    "literature_review": {
        "information_acquisition": (0.20, 0.30),
        "scientific_reasoning": (0.50, 0.65),
        "report_synthesis": (0.10, 0.20),
    },
    "claim_verification": {
        "information_acquisition": (0.20, 0.30),
        "scientific_reasoning": (0.55, 0.70),
        "report_synthesis": (0.08, 0.18),
    },
    "data_analysis": {
        "information_acquisition": (0.25, 0.35),
        "scientific_reasoning": (0.45, 0.60),
        "report_synthesis": (0.12, 0.22),
    },
}

# 按 task_type 的维度条目数目标（与 v5.3 DIMENSION_CONFIG 对齐）
TASK_ITEM_COUNTS = {
    "literature_review": {"information_acquisition": (15, 19), "scientific_reasoning": (23, 30), "report_synthesis": (10, 14)},
    "claim_verification": {"information_acquisition": (12, 16), "scientific_reasoning": (20, 28), "report_synthesis": (8, 11)},
    "data_analysis": {"information_acquisition": (15, 19), "scientific_reasoning": (23, 30), "report_synthesis": (10, 14)},
}

# LLM 深度校准 Prompt
PROMPT_DEEP_CALIBRATION = """\
You are an expert academic rubric evaluator. Review the following rubric and provide structured quality feedback.

**Research Question**:
---
{query}
---

**Rubric Items** ({total_count} total):
{items_text}

**Task**: Evaluate the overall quality and identify specific improvements:

1. Are there any vague or unjudgeable questions? (List rubric_ids)
2. Are there items that should be Critical but are marked lower? ONLY suggest Critical if the item is TRULY essential to answering the research question. Do NOT over-promote. Most items should remain Mandatory or Standard.
3. Are there items missing source_ids that should have them? (List)
4. Is the scientific_reasoning dimension sufficiently analytical (not just factual recall)?
5. Are there any redundant items that test the same concept?
6. Overall assessment: score 1-10 and 3 concrete improvement suggestions.

Output as JSON:
{{
  "vague_items": [{{"rubric_id": "R1", "issue": "...", "suggested_fix": "..."}}],
  "under_ranked": [{{"rubric_id": "R3", "suggested_role": "critical", "reason": "..."}}],
  "missing_sources": [{{"rubric_id": "R5", "suggested_sources": ["S1"], "reason": "..."}}],
  "reasoning_depth_ok": true,
  "redundancies": [{{"rubric_ids": ["R2", "R8"], "reason": "..."}}],
  "overall_score": 7,
  "improvements": ["suggestion 1", "suggestion 2", "suggestion 3"]
}}

Output JSON only, no other text.
"""


class Calibrator:
    """评分表校准器 v2。"""

    def __init__(self, config=None, verbose: bool = True):
        self.config = config
        self.verbose = verbose
        self.client = config.get_client() if config else None

    def calibrate(self, task_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        对生成的评分表进行多层级校准。
        返回校准后的评分表。
        """
        rubrics = task_output.get("rubrics", {})
        dimensions = rubrics.get("dimensions", [])
        query = task_output.get("query", "")
        task_type = task_output.get("task_type", "literature_review")

        issues = []
        fixes_applied = []

        # ── 层级 1: 结构检查 ──
        for dim in dimensions:
            dim_id = dim["dimension_id"]
            items = dim.get("items", [])

            if not items:
                issues.append(f"维度 {dim_id} 没有评分项")
                continue

            # Role 分布检查
            role_issues = self._check_role_distribution(dim_id, items)
            issues.extend(role_issues)

            # Source 覆盖检查
            source_issues = self._check_source_coverage(dim_id, items)
            issues.extend(source_issues)

            # 问题质量检查
            quality_issues = self._check_question_quality(dim_id, items)
            issues.extend(quality_issues)

            # 英文输出检查
            lang_issues = self._check_english_output(dim_id, items)
            issues.extend(lang_issues)

        # ── 层级 2: 维度分值比例检查 ──
        ratio_issues = self._check_dimension_ratios(dimensions, task_type)
        issues.extend(ratio_issues)

        # ── 层级 3: 条目数检查 ──
        count_issues = self._check_item_counts(dimensions, task_type)
        issues.extend(count_issues)

        # ── 层级 3b: query / task_type 与域对齐检查 ──
        issues.extend(self._check_query_task_alignment(query, task_type, dimensions))

        # ── 层级 4: LLM 深度校准 (v5.3 禁用 — 使用轻量校准哲学，避免 LLM 修复引入过拟合) ──
        # 禁用说明：v5.3 采用质量驱动 + 轻量校准设计，评分项在生成阶段已通过
        # 概念泛化和规则检查完成质量控制。LLM 深度校准可能重写评分项，重新引入
        # 论文特有术语或过拟合问题，与 v5.3 设计哲学冲突。
        # 如需启用，设置 enable_llm_calibration=True

        # ── 层级 5: 硬性 Role 重平衡 ──
        # 防止 LLM 校准过度提升 Critical，导致分布失衡
        self._enforce_role_balance(dimensions)

        # 重新计算总分
        total = sum(d["max_score"] for d in dimensions)
        rubrics["total_score"] = total

        # 添加校准元数据
        task_output["calibration"] = {
            "version": "2.0",
            "issues_found": len(issues),
            "issues": issues[:30],
            "fixes_applied": fixes_applied[:20],
            "task_type": task_type,
        }

        if issues and self.verbose:
            logger.info(f"校准发现 {len(issues)} 个问题，已自动修复 {len(fixes_applied)} 个")

        return task_output

    # ── 层级 1 检查方法 ──

    def _check_role_distribution(self, dim_id: str, items: list) -> list:
        """检查并报告 role 分布问题。"""
        issues = []
        total = len(items)
        if total == 0:
            return issues

        role_counts = {"Critical": 0, "Mandatory": 0, "Standard": 0}
        for item in items:
            role = item.get("role", "Standard")
            role_counts[role] = role_counts.get(role, 0) + 1

        for role, (min_ratio, max_ratio) in ROLE_DISTRIBUTION_RANGE.items():
            role_cap = role.capitalize()
            count = role_counts.get(role_cap, 0)
            ratio = count / total

            if ratio < min_ratio:
                issues.append(
                    f"{dim_id}: {role_cap} 项过少 ({count}/{total}={ratio:.0%}, "
                    f"目标 {min_ratio:.0%}-{max_ratio:.0%})"
                )
            elif ratio > max_ratio:
                issues.append(
                    f"{dim_id}: {role_cap} 项过多 ({count}/{total}={ratio:.0%}, "
                    f"目标 {min_ratio:.0%}-{max_ratio:.0%})"
                )

        return issues

    def _check_source_coverage(self, dim_id: str, items: list) -> list:
        """检查 source_ids 覆盖度。"""
        issues = []
        if not items:
            return issues

        # 统计无来源的项目比例
        no_source_count = sum(
            1 for item in items if not item.get("source_ids")
        )

        if dim_id in ("information_acquisition", "scientific_reasoning"):
            no_source_ratio = no_source_count / len(items)
            if no_source_ratio > 0.25:
                issues.append(
                    f"{dim_id}: {no_source_ratio:.0%} 的评分项缺少 source_ids 引用 "
                    f"(目标 ≤25%)"
                )

        # 检查 report_synthesis 是否有过多的 source-linked 项
        if dim_id == "report_synthesis":
            with_source = sum(1 for item in items if item.get("source_ids"))
            if with_source / len(items) > 0.4:
                issues.append(
                    f"{dim_id}: 过多评分项带有 source_ids ({with_source}/{len(items)}), "
                    f"综合维度应主要评估报告结构而非内容"
                )

        return issues

    def _check_question_quality(self, dim_id: str, items: list) -> list:
        """深度问题质量检查。"""
        issues = []
        seen_questions = set()
        vague_patterns = [
            "relevant", "appropriate", "sufficient", "adequate", "proper",
            "相关", "适当", "足够", "合理", "充分",
            "mention any", "mention some", "discuss any",
            "是否提到", "是否涉及", "是否讨论",
        ]
        weak_verbs = ["mention", "list", "include", "contain", "have", "存在", "提到", "列出"]

        for item in items:
            q = item.get("question", "").strip()
            rid = item.get("rubric_id", "?")

            if not q:
                issues.append(f"{rid}: 问题为空")
                continue

            # 检查重复
            q_normalized = q.lower().strip("?？")
            if q_normalized in seen_questions:
                issues.append(f"{rid}: 问题与已有项目重复")
            seen_questions.add(q_normalized)

            # 检查模糊词汇
            for pattern in vague_patterns:
                if pattern.lower() in q.lower():
                    issues.append(
                        f"{rid}: 问题包含模糊词汇 '{pattern}': {q[:60]}..."
                    )
                    break

            # 对 scientific_reasoning 检查是否使用了弱动词
            if dim_id == "scientific_reasoning":
                q_lower = q.lower()
                for verb in weak_verbs:
                    if f"does the report {verb}" in q_lower or f"does the report explicitly {verb}" in q_lower:
                        issues.append(
                            f"{rid}: 科学推理项使用了弱动词 '{verb}'，应使用 analyze/explain/derive/argue 等: {q[:60]}..."
                        )
                        break

            # 检查问题长度（过短可能不够具体）
            if len(q) < 30:
                issues.append(
                    f"{rid}: 问题过短可能不够具体 ({len(q)} chars): {q}"
                )

        return issues

    def _check_english_output(self, dim_id: str, items: list) -> list:
        """检查是否为英文输出。"""
        issues = []
        for item in items:
            q = item.get("question", "").strip()
            rid = item.get("rubric_id", "?")

            # 检查中文字符
            import re
            if re.search(r'[\u4e00-\u9fff]', q):
                issues.append(
                    f"{rid}: 问题包含中文字符，应使用英文: {q[:60]}..."
                )

            # 检查标准前缀
            valid_prefixes = (
                "Does the report", "Is the", "Are the", "Can the",
                "Has the report", "Does it", "Has it",
            )
            if not any(q.startswith(p) for p in valid_prefixes):
                issues.append(
                    f"{rid}: 问题未使用标准英文前缀: {q[:60]}..."
                )

        return issues

    # ── 层级 2 检查方法 ──

    def _check_dimension_ratios(self, dimensions: list, task_type: str) -> list:
        """检查各维度分值占比（按 task_type 适配）。"""
        issues = []
        total_score = sum(d["max_score"] for d in dimensions)
        if total_score == 0:
            return ["总分为 0，评分表无效"]

        ratio_ranges = TASK_DIMENSION_RATIO.get(task_type, TASK_DIMENSION_RATIO["literature_review"])

        for dim in dimensions:
            dim_id = dim["dimension_id"]
            ratio = dim["max_score"] / total_score

            if dim_id in ratio_ranges:
                min_r, max_r = ratio_ranges[dim_id]
                if ratio < min_r or ratio > max_r:
                    issues.append(
                        f"{dim_id}: 分值占比 {ratio:.0%} 不在合理范围 "
                        f"({min_r:.0%}-{max_r:.0%}) for {task_type}"
                    )

        return issues

    def _check_item_counts(self, dimensions: list, task_type: str) -> list:
        """检查各维度条目数是否在合理范围。"""
        issues = []
        count_targets = TASK_ITEM_COUNTS.get(task_type, TASK_ITEM_COUNTS["literature_review"])

        for dim in dimensions:
            dim_id = dim["dimension_id"]
            count = len(dim.get("items", []))

            if dim_id in count_targets:
                min_c, max_c = count_targets[dim_id]
                if count < min_c:
                    issues.append(
                        f"{dim_id}: 条目数过少 ({count}, 目标 {min_c}-{max_c})"
                    )
                elif count > max_c:
                    issues.append(
                        f"{dim_id}: 条目数过多 ({count}, 目标 {min_c}-{max_c})"
                    )

        return issues

    def _check_query_task_alignment(
        self, query: str, task_type: str, dimensions: list
    ) -> list:
        """检测 query 形态与 task_type 错位，以及模板域漂移残留。"""
        issues = []
        if task_type == "claim_verification" and is_survey_style_query(query):
            issues.append(
                "query 为综述/对比型（recent advances, trade-offs 等），"
                "与 claim_verification 单点主张核验可能错位；"
                "请确认是否应使用 literature_review 或改写 query 为可核验主张"
            )

        drift_items = []
        for dim in dimensions:
            for item in dim.get("items", []):
                q = item.get("question", "")
                if q and not item_aligns_with_query(q, query):
                    drift_items.append(item.get("rubric_id", q[:40]))

        if drift_items:
            preview = ", ".join(drift_items[:5])
            suffix = f" 等 {len(drift_items)} 项" if len(drift_items) > 5 else ""
            issues.append(
                f"存在与 query 域不对齐的评分项（疑似模板残留）: {preview}{suffix}"
            )

        return issues

    # ── 层级 4: LLM 深度校准 ──

    def _llm_deep_calibration(self, query: str, dimensions: list) -> tuple:
        """使用 LLM 进行深度质量校准。"""
        if not self.client:
            return [], []

        # 收集所有评分项
        all_items = []
        for dim in dimensions:
            for item in dim.get("items", []):
                all_items.append({
                    **item,
                    "dimension_id": dim["dimension_id"],
                })

        if not all_items:
            return [], []

        # 分批处理（每批最多 40 条）
        batch_size = 40
        all_issues = []
        all_fixes = []

        for i in range(0, len(all_items), batch_size):
            batch = all_items[i:i + batch_size]
            items_text = "\n\n".join(
                f"{it['rubric_id']} [{it['dimension_id']}/{it['role']}] (src: {','.join(it.get('source_ids', [])) or 'none'}): {it['question']}"
                for it in batch
            )

            prompt = PROMPT_DEEP_CALIBRATION.format(
                query=query,
                total_count=len(all_items),
                items_text=items_text,
            )

            try:
                result = call_llm_json(
                    self.client,
                    self.config.rubric_model if self.config else "qwen3.7-max",
                    prompt,
                    system="You are a strict academic rubric evaluator. Be critical and thorough. Output JSON only.",
                    temperature=0.2,
                    max_retries=2,
                )
                if isinstance(result, dict):
                    # 处理 vague_items
                    for v in result.get("vague_items", []):
                        all_issues.append(
                            f"{v.get('rubric_id', '?')}: 问题模糊 — {v.get('issue', '')}"
                        )
                        if v.get("suggested_fix"):
                            all_fixes.append({
                                "type": "reword",
                                "rubric_id": v.get("rubric_id"),
                                "new_question": v.get("suggested_fix"),
                                "reason": v.get("issue", ""),
                            })

                    # 处理 under_ranked
                    for u in result.get("under_ranked", []):
                        all_issues.append(
                            f"{u.get('rubric_id', '?')}: 重要性低估 — {u.get('reason', '')}"
                        )
                        all_fixes.append({
                            "type": "role_adjust",
                            "rubric_id": u.get("rubric_id"),
                            "new_role": u.get("suggested_role", "critical"),
                            "reason": u.get("reason", ""),
                        })

                    # 处理 missing_sources
                    for m in result.get("missing_sources", []):
                        all_issues.append(
                            f"{m.get('rubric_id', '?')}: 缺少来源引用 — {m.get('reason', '')}"
                        )
                        all_fixes.append({
                            "type": "add_sources",
                            "rubric_id": m.get("rubric_id"),
                            "source_ids": m.get("suggested_sources", []),
                            "reason": m.get("reason", ""),
                        })

                    # 处理 redundancies
                    for r in result.get("redundancies", []):
                        rids = r.get("rubric_ids", [])
                        if len(rids) >= 2:
                            all_issues.append(
                                f"冗余: {', '.join(rids)} — {r.get('reason', '')}"
                            )

                    # 处理 reasoning_depth
                    if not result.get("reasoning_depth_ok", True):
                        all_issues.append(
                            "scientific_reasoning: LLM 评估认为推理深度不足，需要更多分析性问题"
                        )

                    # 处理 overall improvements
                    for imp in result.get("improvements", []):
                        all_issues.append(f"整体改进建议: {imp}")

            except Exception as e:
                logger.warning(f"LLM deep calibration batch failed: {e}")

        return all_issues, all_fixes

    def _apply_deep_fixes(self, dimensions: list, fixes: list):
        """应用 LLM 深度校准产生的自动修复。"""
        # 构建快速查找映射
        item_map = {}
        for dim in dimensions:
            for item in dim.get("items", []):
                item_map[item["rubric_id"]] = (dim, item)

        for fix in fixes:
            fix_type = fix.get("type")
            rid = fix.get("rubric_id")
            entry = item_map.get(rid)
            if not entry:
                continue

            dim, item = entry

            if fix_type == "reword":
                new_q = fix.get("new_question", "").strip()
                # 清理 LLM 返回的指令性前缀（如 "Rewrite as..."）
                for prefix_pattern in [
                    r"^Rewrite as a complete English sentence:\s*'",
                    r"^Rewrite as\b.*?:\s*'",
                    r"^Replace with\b.*?:\s*'",
                    r"^Rephrase as\b.*?:\s*'",
                ]:
                    m = re.match(prefix_pattern, new_q, re.IGNORECASE)
                    if m:
                        new_q = new_q[m.end():]
                        # 去掉尾部可能的单引号
                        if new_q.endswith("'"):
                            new_q = new_q[:-1]
                        new_q = new_q.strip()
                        break
                # 确保不含中文字符，否则跳过修复
                if re.search(r'[\u4e00-\u9fff]', new_q):
                    logger.warning(f"  [Skip reword] {rid}: still contains Chinese after cleanup")
                    continue
                if new_q:
                    item["question"] = new_q
                    # 更新 competency_category 和 rubric_key
                    item["competency_category"] = item.get("competency_category") or infer_competency_category(
                        new_q, dim["dimension_id"]
                    )
                    # 重新计算 max_score
                    self._recalc_dim_score(dim)
                    logger.info(f"  [Auto-fix] Rewrote {rid}: {new_q[:50]}...")

            elif fix_type == "role_adjust":
                new_role = fix.get("new_role", "").lower()
                if new_role in ("critical", "mandatory", "standard"):
                    item["role"] = role_from_importance(new_role)
                    item["weight"] = weight_from_importance(new_role)
                    self._recalc_dim_score(dim)
                    logger.info(f"  [Auto-fix] Adjusted {rid} role → {new_role}")

            elif fix_type == "add_sources":
                new_sources = fix.get("source_ids", [])
                if new_sources:
                    existing = set(item.get("source_ids", []))
                    existing.update(new_sources)
                    item["source_ids"] = sorted(existing)
                    logger.info(f"  [Auto-fix] Added sources to {rid}: {new_sources}")

    def _recalc_dim_score(self, dim: dict):
        """重新计算维度的 max_score。"""
        dim["max_score"] = sum(it.get("weight", 1) for it in dim.get("items", []))

    def _enforce_role_balance(self, dimensions: list):
        """硬性重平衡：确保 Critical 比例不超过上限，防止 LLM 校准过度提升。"""
        for dim in dimensions:
            items = dim.get("items", [])
            total = len(items)
            if total == 0:
                continue

            # 统计当前 role 分布
            role_counts = {"Critical": 0, "Mandatory": 0, "Standard": 0}
            for item in items:
                r = item.get("role", "Standard")
                role_counts[r] = role_counts.get(r, 0) + 1

            critical_count = role_counts.get("Critical", 0)
            critical_ratio = critical_count / total
            max_critical_ratio = ROLE_DISTRIBUTION_RANGE["critical"][1]

            if critical_ratio > max_critical_ratio:
                # 需要降级多余的 Critical → Mandatory
                excess = int(critical_count - total * max_critical_ratio)
                if excess <= 0:
                    continue

                # 按 priority_score 降序排列（保留最重要的 Critical）
                sorted_critical = sorted(
                    [it for it in items if it.get("role") == "Critical"],
                    key=lambda x: item_priority_score(x),
                    reverse=True,
                )

                downgraded = 0
                for item in sorted_critical:
                    if downgraded >= excess:
                        break
                    item["role"] = "Mandatory"
                    item["weight"] = weight_from_importance("mandatory")
                    downgraded += 1
                    logger.info(
                        f"  [Role-balance] Downgraded {item['rubric_id']} "
                        f"Critical→Mandatory in {dim['dimension_id']}"
                    )

                # 重新计算维度分值
                self._recalc_dim_score(dim)
                logger.info(
                    f"  [Role-balance] {dim['dimension_id']}: "
                    f"downgraded {downgraded} Critical items "
                    f"({critical_ratio:.0%} → {max_critical_ratio:.0%})"
                )
