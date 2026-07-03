"""学术 Skill 共享 LLM 执行器（适配外部 Academic-* / Paper-* 能力清单）。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.services.qwen_client import qwen_structured_chat

logger = logging.getLogger(__name__)

DEFAULT_RESPONSE_SCHEMA = {
    "summary": "string — 核心结论摘要",
    "findings": ["string — 结构化发现/要点"],
    "recommendations": ["string — 可执行建议"],
    "quality_score": "integer 0-100",
    "warnings": ["string — 风险或不足"],
}

ACADEMIC_SKILL_SPECS: Dict[str, Dict[str, Any]] = {
    "paper_reading": {
        "title": "论文精读",
        "instruction": (
            "对给定论文摘要/片段进行结构化精读：研究问题、方法、关键结果、局限与对本项目的启示。"
            "禁止编造未出现在输入中的实验数据。"
        ),
    },
    "deep_research": {
        "title": "深度文献调研",
        "instruction": (
            "基于研究问题与已有文献事实，给出深度调研摘要：主流路线、争议点、空白与下一步检索关键词。"
        ),
    },
    "source_tracing": {
        "title": "来源追溯",
        "instruction": (
            "追溯主张与引用的对应关系，标注哪些结论有 chunk/DOI 支撑，哪些缺少可追溯来源。"
        ),
    },
    "research_genealogy": {
        "title": "研究谱系",
        "instruction": (
            "梳理该研究问题的学术谱系：经典工作、演进脉络、当前前沿分支，以时间线或流派形式呈现。"
        ),
    },
    "claude_scholar": {
        "title": "学术综合",
        "instruction": (
            "以学者视角综合文献事实与假设，给出跨论文的机制解释与可检验推论。"
        ),
    },
    "paper_skill": {
        "title": "论文分析",
        "instruction": (
            "提取论文的核心贡献、实验设计要点、可复用方法与对本假设验证的借鉴价值。"
        ),
    },
    "question_validator": {
        "title": "研究问题校验",
        "instruction": (
            "评估研究问题是否具体、可检验、边界清晰；指出模糊处并给出改写建议。"
        ),
    },
    "academic_research": {
        "title": "学术研究框架",
        "instruction": (
            "将研究问题拆解为：背景动机、核心科学问题、可验证子问题与预期知识增量。"
        ),
    },
    "research_skills": {
        "title": "研究设计要点",
        "instruction": (
            "列出完成该研究所需的关键能力、资源与里程碑，对齐假设验证路径。"
        ),
    },
    "academic_writing": {
        "title": "学术写作润色",
        "instruction": (
            "对报告章节进行学术写作诊断：逻辑链、术语一致性、论证强度，给出段落级修改建议。"
            "不要引入大模型/智能体等平台描述。"
        ),
    },
    "write_chinese": {
        "title": "中文学术表达",
        "instruction": (
            "优化中文学术表述：术语规范、句式简洁、避免口语化与翻译腔，保留必要英文专名。"
        ),
    },
    "paper_writer": {
        "title": "论文章节起草",
        "instruction": (
            "根据已有章节内容，起草或补全缺失段落（Problem/Rationale/Methods 等），保持与假设一致。"
        ),
    },
    "academic_paper": {
        "title": "学术论文结构",
        "instruction": (
            "检查报告是否符合学术论文 IMRaD 逻辑：引言-方法-结果-讨论是否完整、层次是否清晰。"
        ),
    },
    "empirical_paper": {
        "title": "实证论文规范",
        "instruction": (
            "按实证研究规范审查：变量定义、对照组、样本量、统计方法、可重复性说明是否充分。"
        ),
    },
    "nature_paper": {
        "title": "顶刊叙事结构",
        "instruction": (
            "按 Nature/Science 类短论文叙事：突出问题重要性、核心发现、广泛意义；建议摘要与图注结构。"
        ),
    },
    "ccfa_skill": {
        "title": "CCF-A 会议规范",
        "instruction": (
            "从计算机顶会论文角度审查：问题定义、baseline、消融、复杂度与实验公平性。"
        ),
    },
    "paper_pilot": {
        "title": "论文写作路线图",
        "instruction": (
            "生成从当前研究计划到可投稿论文的分阶段路线图：待补实验、图表、写作任务与优先级。"
        ),
    },
    "paper_to_patent": {
        "title": "论文转专利要点",
        "instruction": (
            "从研究内容提取可专利的技术方案要点：独立权利要求方向、实施例要素（非法律定稿）。"
        ),
    },
    "paper_to_storyboard": {
        "title": "论文转故事板",
        "instruction": (
            "将研究叙事转化为 4-6 帧故事板：每帧标题、视觉元素、旁白要点，便于汇报展示。"
        ),
    },
    "paper2beamer": {
        "title": "Beamer 幻灯片大纲",
        "instruction": (
            "生成 Beamer 演示文稿大纲：章节标题、每页要点、建议图表占位，适合 15 分钟学术报告。"
        ),
    },
}


def _truncate_json(obj: Any, max_chars: int = 10000) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n... (truncated)"


def build_academic_prompt(
    spec_key: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
) -> str:
    spec = ACADEMIC_SKILL_SPECS[spec_key]
    rq = (
        input_data.get("research_question")
        or context.get("research_question")
        or ""
    )
    content = input_data.get("content") or input_data.get("text") or input_data.get("chapters")
    if content is None:
        content = {
            k: v
            for k, v in input_data.items()
            if k not in ("research_question", "skill_options") and v
        }
    return f"""你是一位严谨的学术助手，正在执行「{spec['title']}」任务。

研究问题：{rq or '（未提供）'}

任务要求：
{spec['instruction']}

输入材料：
{_truncate_json(content)}

请输出 JSON（中文），字段：
- summary: 核心结论（150字以内）
- findings: 3-8 条结构化发现
- recommendations: 3-6 条可执行建议
- quality_score: 0-100 质量/就绪度评分
- warnings: 0-4 条风险或信息不足提示

要求：基于输入材料推理，不得编造未给出的文献或实验结果。"""


def run_academic_llm(
    spec_key: str,
    input_data: Dict[str, Any],
    context: Dict[str, Any],
    *,
    prompt_version: str,
    temperature: float = 0.25,
) -> Dict[str, Any]:
    prompt = build_academic_prompt(spec_key, input_data, context)
    schema_example = {
        "summary": "示例摘要",
        "findings": ["发现1", "发现2"],
        "recommendations": ["建议1"],
        "quality_score": 75,
        "warnings": [],
    }
    try:
        raw = qwen_structured_chat(
            prompt=prompt,
            schema_example=schema_example,
            prompt_version=prompt_version,
            temperature=temperature,
        )
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
    except Exception as exc:
        logger.warning("Academic skill LLM 失败 (%s): %s", spec_key, exc)
    return fallback_academic_output(spec_key, input_data)


def fallback_academic_output(spec_key: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    spec = ACADEMIC_SKILL_SPECS.get(spec_key, {})
    has_input = bool(input_data)
    return {
        "summary": f"{spec.get('title', spec_key)}：输入材料"
        + ("已接收，建议补充更多上下文后重试。" if has_input else "不足，无法深入分析。"),
        "findings": ["已记录输入要点，待 LLM 可用后生成完整分析"],
        "recommendations": ["补充文献事实或报告章节后重新运行该 Skill"],
        "quality_score": 40 if has_input else 15,
        "warnings": ["LLM 不可用或调用失败，当前为规则降级输出"],
    }
