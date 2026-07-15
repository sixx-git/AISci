"""
评分表辅助工具：
1. 统一 importance / role / weight 转换
2. 推断评分项的能力类别
3. 生成稳定语义锚点 rubric_key
4. 规范化问题文本
"""

from __future__ import annotations

import re
from typing import Dict


ROLE_TO_WEIGHT: Dict[str, int] = {
    "critical": 4,
    "mandatory": 2,
    "standard": 1,
}


def normalize_importance(value: str) -> str:
    """将 Critical / critical / Mandatory 等统一为小写。"""
    return (value or "standard").strip().lower()


def weight_from_importance(value: str) -> int:
    return ROLE_TO_WEIGHT.get(normalize_importance(value), 1)


def role_from_importance(value: str) -> str:
    return normalize_importance(value).capitalize()


def normalize_question_text(question: str) -> str:
    """
    轻量规范化问题文本。
    
    对于英文评分表（gen-2）：保持英文格式，统一为 "Does the report..." 前缀。
    对于中文评分表（gen-1）：保持原有中文格式。
    """
    q = (question or "").strip()
    if not q:
        return q

    q = re.sub(r"\s+", " ", q)

    # 判断是否为英文评分表（不包含中文字符，或以英文前缀开头）
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', q))
    has_english_prefix = q.startswith(("Does the report", "Is the", "Are the", "Can the", "Has the report"))

    if has_english_prefix and not has_chinese:
        # 英文评分表，保持原样
        if not q.endswith("?"):
            q = q + "?"
        return q

    if has_chinese:
        # 中文评分表，保持原有中文逻辑
        allowed_prefixes = (
            "报告是否",
            "Does the report",
            "Is the",
            "Are the",
            "Can the",
            "Has the report",
        )
        if q.startswith(allowed_prefixes):
            return q

        if "是否" in q:
            suffix = q.split("是否", 1)[1].strip()
            q = f"报告是否{suffix}"
        elif q.startswith("报告"):
            q = q.replace("报告", "报告是否", 1)
        else:
            q = f"报告是否{q}"

        if q.endswith(("?", "？")):
            return q
        return q + "？"

    # 纯英文但无标准前缀
    if not has_english_prefix:
        # 检查是否为 "[Topic prefix]: Does the report..." 格式（SR 维度常见）
        # 如果冒号后面已经包含 "Does the report"，则保持原样
        topic_match = re.match(r'^([A-Z][A-Za-z\s/]+):\s+(Does the report|Is the|Are the)\b', q)
        if topic_match:
            pass  # 保持 "[Topic]: Does the report..." 格式
        else:
            q = f"Does the report {q}"
    if not q.endswith("?"):
        q = q + "?"
    return q


def infer_competency_category(question: str, dimension_id: str) -> str:
    """
    从问题文本粗略推断能力类别。
    该类别不是最终语义金标准，但足够作为稳定锚点与覆盖检查的基础。
    """
    q = (question or "").lower()

    if dimension_id == "report_synthesis":
        if any(k in q for k in ["引用", "source", "cite", "标注来源"]):
            return "citation"
        if any(k in q for k in ["图表", "表格", "可视化", "chart", "figure"]):
            return "visualization"
        if any(k in q for k in ["结构", "章节", "摘要", "结论", "section"]):
            return "structure"
        if any(k in q for k in ["术语", "表达", "语言", "专业"]):
            return "language"
        if any(k in q for k in ["建议", "未来", "改进", "方向"]):
            return "recommendation"
        return "synthesis"

    if any(k in q for k in ["定义", "definition", "术语", "概念"]):
        return "definition"
    if any(k in q for k in ["机制", "原因", "因果", "why", "how", "失效"]):
        return "mechanism"
    if any(k in q for k in ["对比", "比较", "差异", "优劣", "compare"]):
        return "comparison"
    if any(k in q for k in ["局限", "边界", "限制", "不足", "条件"]):
        return "limitation"
    if any(k in q for k in ["数据", "参数", "数值", "数据集", "实验"]):
        return "evidence"
    if any(k in q for k in ["推理", "综合", "评估", "裁定", "判断", "充分性"]):
        return "synthesis"

    if dimension_id == "information_acquisition":
        return "evidence"
    if dimension_id == "scientific_reasoning":
        return "mechanism"
    return "synthesis"


def build_rubric_key(dimension_id: str, competency_category: str, question: str) -> str:
    """
    构建稳定语义锚点：
    dimension.category.slug
    """
    q = normalize_question_text(question)
    slug = q.lower()
    slug = re.sub(r"[（()）\[\]{}]", " ", slug)
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if len(slug) > 48:
        slug = slug[:48].rstrip("_")
    if not slug:
        slug = "item"
    return f"{dimension_id}.{competency_category}.{slug}"


def item_priority_score(item: dict) -> float:
    """
    用于校准阶段决定哪些条目更适合保留/提升。
    分数越高，越值得保留。
    """
    importance = normalize_importance(item.get("importance") or item.get("role", "standard"))
    question = (item.get("question") or "").lower()
    category = item.get("competency_category") or infer_competency_category(
        item.get("question", ""),
        item.get("dimension_id", ""),
    )
    source_count = len(item.get("source_ids", []) or [])

    score = float(weight_from_importance(importance))
    score += min(source_count, 3) * 0.8

    if category in ("mechanism", "limitation", "synthesis"):
        score += 1.2
    elif category in ("comparison", "evidence", "structure", "citation"):
        score += 0.7

    if any(k in question for k in ["分析", "推理", "评估", "比较", "原因", "why", "compare"]):
        score += 0.9
    if any(k in question for k in ["排版", "美观", "整洁"]):
        score -= 0.8

    return score
