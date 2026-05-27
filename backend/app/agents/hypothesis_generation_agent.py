"""
假设生成智能体 (HypothesisGenerationAgent)
——基于文献事实的归纳/演绎推理，生成可追溯的科学假设。
"""
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.qwen_client import qwen_structured_chat
from app.services.prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class HypothesisItem(BaseModel):
    """单个假设项 —— 每条假设备绑定真实文献事实"""
    hypothesis: str = Field(..., description="假设内容")
    rationale: str = Field(..., description="理论依据")
    novelty: str = Field(..., description="创新性")
    testability: str = Field(..., description="可测试性")
    required_data: str = Field(..., description="所需数据")
    possible_method: str = Field(..., description="可能的方法")
    risk: str = Field(..., description="风险")
    supporting_fact_ids: List[str] = Field(default_factory=list, description="支持的文献事实 ID 列表")
    evidence_level: str = Field(default="medium", description="证据级别: high / medium / low")


class HypothesisGenerationResult(BaseModel):
    """假设生成结果"""
    hypotheses: List[HypothesisItem] = Field(..., description="生成的假设列表")
    summary: Optional[str] = Field(None, description="生成摘要")


class HypothesisGenerationAgent:
    """
    假设生成智能体

    工作流程：
      1. 格式化事实（含 fact_id）→ 传入 Prompt
      2. LLM 基于已知事实进行归纳与演绎推理
      3. 每条假设必须包含 supporting_fact_ids
      4. 后校验：验 fact_id 真实性、标的证据级别
    """

    def __init__(self):
        pass

    def generate(
        self,
        research_question: str,
        facts: List[Dict[str, Any]],
        knowledge_gaps: List[Dict[str, Any]],
        constraints: List[str],
        project_id: Optional[str] = None
    ) -> HypothesisGenerationResult:
        """
        生成科学假设

        Args:
            research_question: 研究问题
            facts: 事实列表（来自 LiteratureMiningAgent.facts）
            knowledge_gaps: 知识缺口列表
            constraints: 约束条件列表
            project_id: 项目ID（可选）

        Returns:
            生成的假设结果
        """
        try:
            logger.info(f"开始生成假设，研究问题：{research_question[:100]}..., facts 数量：{len(facts)}")

            # ── 构建可用 fact_id 白名单 ──
            available_fact_ids = self._collect_fact_ids(facts)

            # ── 格式化输入 ──
            formatted_facts = self._format_facts(facts)
            formatted_gaps = self._format_gaps(knowledge_gaps)
            formatted_constraints = self._format_constraints(constraints)

            # ── 构建 Prompt ──
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "hypothesis_generation",
                {
                    "research_question": research_question,
                    "formatted_facts": formatted_facts,
                    "formatted_gaps": formatted_gaps,
                    "formatted_constraints": formatted_constraints,
                    "available_fact_ids": json.dumps(available_fact_ids, ensure_ascii=False),
                    "facts_empty": "true" if not facts else "false",
                },
            )

            # ── Schema example（含新字段） ──
            schema_example = {
                "hypotheses": [
                    {
                        "hypothesis": "清晰、具体、可检验的假设陈述",
                        "rationale": "基于归纳/演绎推理的详细理由，引用相关事实",
                        "novelty": "明确说明创新性，与现有研究的区别",
                        "testability": "详细说明如何验证，包括实验设计或分析方法",
                        "required_data": "具体列出所需的数据类型、来源和数量",
                        "possible_method": "可能的研究方法和技术路线",
                        "risk": "可能的风险、挑战和局限性",
                        "supporting_fact_ids": ["fact_001", "fact_002"],
                        "evidence_level": "medium",
                    }
                ],
                "summary": "对生成假设的简要总结和建议",
            }

            # ── 调用 LLM ──
            result_dict = qwen_structured_chat(
                prompt=prompt,
                schema_example=schema_example,
                prompt_version="hypothesis_generation",
            )

            # ── 后校验：验证 supporting_fact_ids → 补 evidence_level ──
            result = self._validate_and_normalize_result(result_dict, available_fact_ids, facts)

            logger.info(f"成功生成 {len(result.hypotheses)} 条假设")

            return result

        except Exception as e:
            logger.error(f"生成假设时出错：{e}", exc_info=True)
            raise

    # ────────── 格式化 ──────────

    def _collect_fact_ids(self, facts: List[Dict[str, Any]]) -> List[str]:
        """收集所有可用 fact_id 构建白名单"""
        ids = []
        for fact in facts:
            fid = fact.get("fact_id")
            if fid:
                ids.append(fid)
        return ids

    def _format_facts(self, facts: List[Dict[str, Any]]) -> str:
        """格式化事实列表（含 fact_id、source、quote），方便 LLM 引用"""
        if not facts:
            return "（当前项目无已知文献事实 —— 请基于知识缺口和理论推测生成假设，但需明确标注 evidence_level = \"low\"）"

        formatted = []
        for idx, fact in enumerate(facts, 1):
            fid = fact.get("fact_id", f"fact_{idx}")
            content = fact.get("fact_text") or fact.get("content", str(fact))
            source = fact.get("source_paper_title", fact.get("source", ""))
            quote = fact.get("quote_text", "")
            page = fact.get("page_number", "")

            lines = [f"### Fact {idx} (ID: {fid})"]
            lines.append(f"陈述: {content}")
            if source:
                lines.append(f"来源: {source}")
            if page:
                lines.append(f"页码: p.{page}")
            if quote:
                lines.append(f"原文引用: {quote}")
            lines.append("")

            formatted.append("\n".join(lines))

        return "\n".join(formatted)

    def _format_gaps(self, gaps: List[Dict[str, Any]]) -> str:
        """格式化知识缺口列表"""
        if not gaps:
            return "（无知识缺口）"

        formatted = []
        for idx, gap in enumerate(gaps, 1):
            desc = gap.get("description", gap.get("gap", str(gap)))
            value = gap.get("potential_value", "")
            if value:
                formatted.append(f"{idx}. {desc}\n   研究价值：{value}")
            else:
                formatted.append(f"{idx}. {desc}")

        return "\n".join(formatted)

    def _format_constraints(self, constraints: List[str]) -> str:
        """格式化约束条件列表"""
        if not constraints:
            return "（无约束条件）"

        return "\n".join([f"{idx}. {c}" for idx, c in enumerate(constraints, 1)])

    # ────────── 校验 ──────────

    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        available_fact_ids: List[str],
        facts: List[Dict[str, Any]],
    ) -> HypothesisGenerationResult:
        """
        验证并标准化 LLM 输出：
          - ensuring supporting_fact_ids 只引用 real fact_ids
          - 自动标的 evidence_level
          - 过滤无效假设
        """
        # 确保必要字段存在
        if "hypotheses" not in result_dict or not isinstance(result_dict["hypotheses"], list):
            result_dict["hypotheses"] = []

        fact_id_set = set(available_fact_ids)
        validated_hypotheses = []

        for hypo in result_dict["hypotheses"]:
            if not isinstance(hypo, dict):
                continue

            # 确保所有必要字段存在
            for field in ["hypothesis", "rationale", "novelty", "testability",
                           "required_data", "possible_method", "risk"]:
                if field not in hypo:
                    hypo[field] = ""

            # ── 校验 supporting_fact_ids ──
            raw_ids = hypo.get("supporting_fact_ids", [])
            if not isinstance(raw_ids, list):
                raw_ids = [raw_ids] if raw_ids else []

            validated_ids = [fid for fid in raw_ids if fid in fact_id_set]
            invalid_ids = [fid for fid in raw_ids if fid not in fact_id_set]

            if invalid_ids:
                logger.warning(
                    f"假设 \"{hypo.get('hypothesis', '?')[:60]}...\" 引用了不存在的 fact_id: {invalid_ids}，已过滤"
                )

            hypo["supporting_fact_ids"] = validated_ids

            # ── 自动标的 evidence_level ──
            hypo["evidence_level"] = self._determine_evidence_level(
                raw_level=hypo.get("evidence_level", ""),
                validated_ids=validated_ids,
                facts_available=bool(available_fact_ids),
            )

            validated_hypotheses.append(HypothesisItem(**hypo))

        # 限制 3-5 条
        if len(validated_hypotheses) < 3:
            logger.warning(f"生成的假设数量不足 3 条，实际：{len(validated_hypotheses)}")
        if len(validated_hypotheses) > 5:
            logger.warning(f"生成的假设数量超过 5 条，截断为 5 条")
            validated_hypotheses = validated_hypotheses[:5]

        result_dict["hypotheses"] = validated_hypotheses

        return HypothesisGenerationResult(**result_dict)

    def _determine_evidence_level(
        self,
        raw_level: str,
        validated_ids: List[str],
        facts_available: bool,
    ) -> str:
        """
        标的证据等级：
          - low:    没有事实可引用 / 0 个 supporting_fact_ids
          - medium: 有 1-2 个 supporting_fact_ids
          - high:   3+ 个 supporting_fact_ids
        """
        # LLM 给出的可能是 "low" / "medium" / "high"
        raw = raw_level.lower().strip()

        if not facts_available:
            return "low"

        if len(validated_ids) >= 3:
            return "high"
        elif len(validated_ids) >= 1:
            return "medium"
        else:
            return "low"


# 全局单例
_agent_instance: Optional[HypothesisGenerationAgent] = None


def get_hypothesis_generation_agent() -> HypothesisGenerationAgent:
    """获取 HypothesisGenerationAgent 单例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = HypothesisGenerationAgent()
    return _agent_instance