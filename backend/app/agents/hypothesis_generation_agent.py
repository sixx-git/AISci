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
    question_alignment: str = Field(default="", description="假设与研究问题的对齐说明")
    dataset_field_refs: List[str] = Field(default_factory=list, description="引用的数据集字段")
    data_evidence_ids: List[str] = Field(default_factory=list, description="引用的数据证据 ID")
    validation_target: str = Field(default="", description="验证目标指标，如 Accuracy/F1/AUC")
    expected_measurable_effect: str = Field(default="", description="预期的可量化效果")
    alignment_score: Optional[int] = Field(default=None, description="对齐分数 0-100")
    off_topic: bool = Field(default=False, description="是否偏题")


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

    _QUESTION_DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
        "medical_neuro": {
            "肠道菌群", "肠道微生物", "肠", "gut", "阿尔茨海默", "alzheimer",
            "帕金森", "parkinson", "SCFA", "短链脂肪酸", "粪便", "fecal",
            "大脑皮层", "cerebral cortex", "海马体", "hippocampus",
            "神经退行", "neurodegen", "amyloid", "tau", "小胶质细胞",
            "microglia", "炎症因子", "inflammatory", "血脂屏障",
            "blood-brain barrier", "抑郁症", "depression", "焦虑", "anxiety",
        },
        "medical_oncology": {
            "tumor", "癌", "cancer", "肿瘤", "oncology", "抗原", "antigen",
            "免疫细胞", "immune cell", "T细胞",
        },
        "medical_clinical": {
            "临床", "药", "随机对照", "RCT", "药物", "药理学",
            "流行病", "epidemiology", "公共卫生", "public health",
            "疫苗", "vaccine", "病毒", "virus", "细菌", "bacteria",
        },
        "biology_molecular": {
            "基因编辑", "CRISPR", "genome edit", "干细胞", "stem cell",
            "蛋白", "protein", "酶", "enzyme", "DNA", "RNA", "核苷酸",
            "nucleotide", "细胞凋亡", "apoptosis", "信号通路",
            "signaling pathway", "受体", "receptor",
        },
        "social_policy": {
            "社会经济", "socioeconomic", "教育", "education", "政治", "politics",
            "政策", "policy",
        },
        "psychology": {
            "心理", "psychology",
        },
    }

    OFF_DOMAIN_KEYWORDS = {
        "肠道菌群", "肠道微生物", "gut microbiota", "gut microbiome",
        "阿尔茨海默", "Alzheimer", "帕金森", "Parkinson",
        "SCFA", "短链脂肪酸", "short-chain fatty acid",
        "肿瘤", "癌症", "tumor", "cancer", "癌",
        "药物", "药物靶点", "drug", "药理学",
        "流行病", "传染病", "感染", "临床",
        "心血管", "心肌", "coronary", "cardiovascular",
        "中医", "中药", "针灸",
    }

    def _detect_question_domain(self, question: str) -> Set[str]:
        """从研究问题中检测所属领域"""
        lower_q = question.lower()
        domains: Set[str] = set()
        for domain, keywords in self._QUESTION_DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in lower_q:
                    domains.add(domain)
                    break
        return domains

    def _is_keyword_in_domains(self, keyword_lower: str, domains: Set[str]) -> bool:
        """检查关键词是否属于给定领域"""
        for domain, keywords in self._QUESTION_DOMAIN_KEYWORDS.items():
            if domain in domains:
                for kw in keywords:
                    if kw.lower() in keyword_lower or keyword_lower in kw.lower():
                        return True
        return False

    def generate(
        self,
        research_question: str,
        facts: List[Dict[str, Any]],
        knowledge_gaps: List[Dict[str, Any]],
        constraints: List[str],
        project_id: Optional[str] = None,
        data_context: Optional[Dict[str, Any]] = None,
        multimodal_datasets: Optional[List[Dict[str, Any]]] = None,
        data_linking_evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> HypothesisGenerationResult:
        """
        生成科学假设

        Args:
            research_question: 研究问题
            facts: 事实列表（来自 LiteratureMiningAgent.facts）
            knowledge_gaps: 知识缺口列表
            constraints: 约束条件列表
            project_id: 项目ID（可选）
            data_context: 项目数据上下文（数据集摘要、统计信息等）
            multimodal_datasets: 多模态数据集列表
            data_linking_evidence: 文献事实与数据字段的关联证据

        Returns:
            生成的假设结果
        """
        try:
            data_context = data_context or {}
            multimodal_datasets = multimodal_datasets or []
            data_linking_evidence = data_linking_evidence or []

            logger.info(f"开始生成假设，研究问题：{research_question[:100]}..., facts 数量：{len(facts)}, "
                        f"datasets: {len(multimodal_datasets)}, linking_evidence: {len(data_linking_evidence)}")

            # ── 构建可用 fact_id 白名单 ──
            available_fact_ids = self._collect_fact_ids(facts)

            # ── 格式化输入 ──
            formatted_facts = self._format_facts(facts)
            formatted_gaps = self._format_gaps(knowledge_gaps)
            formatted_constraints = self._format_constraints(constraints)
            formatted_data_context = self._format_data_context(
                data_context, multimodal_datasets, data_linking_evidence
            )

            # ── 构建 Prompt ──
            prompt_loader = get_prompt_loader()
            prompt = prompt_loader.render_template(
                "hypothesis_generation",
                {
                    "research_question": research_question,
                    "formatted_facts": formatted_facts,
                    "formatted_gaps": formatted_gaps,
                    "formatted_constraints": formatted_constraints,
                    "formatted_data_context": formatted_data_context,
                    "available_fact_ids": json.dumps(available_fact_ids, ensure_ascii=False),
                    "facts_empty": "true" if not facts else "false",
                    "data_context_empty": "true" if not data_context and not multimodal_datasets else "false",
                },
            )

            # ── Schema example（含新字段） ──
            schema_example = {
                "hypotheses": [
                    {
                        "hypothesis": "清晰、具体、可检验的假设陈述",
                        "question_alignment": "该假设直接针对 [研究问题关键词] 中的 [指标]，通过[方法]验证",
                        "rationale": "基于归纳/演绎推理的详细理由，引用相关事实",
                        "novelty": "明确说明创新性，与现有研究的区别",
                        "testability": "详细说明如何验证，包括实验设计或分析方法",
                        "required_data": "具体列出所需的数据类型、来源和数量，优先引用已上传数据集",
                        "possible_method": "可能的研究方法和技术路线，必须与研究问题一致",
                        "risk": "可能的风险、挑战和局限性",
                        "supporting_fact_ids": ["fact_001", "fact_002"],
                        "dataset_field_refs": ["dataset.behavior_label", "dataset.cnn_features"],
                        "data_evidence_ids": ["evidence_001"],
                        "validation_target": "Accuracy / F1-score / AUC",
                        "expected_measurable_effect": "相对基线方法提升 5%-10%",
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

            # ── 后校验 ──
            result = self._validate_and_normalize_result(
                result_dict, available_fact_ids, facts,
                research_question=research_question,
            )

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

    def _format_data_context(
        self,
        data_context: Dict[str, Any],
        multimodal_datasets: List[Dict[str, Any]],
        data_linking_evidence: List[Dict[str, Any]],
    ) -> str:
        """格式化数据上下文"""
        parts = []

        if data_context:
            parts.append("## 项目数据上下文")
            if data_context.get("dataset_summary"):
                parts.append(f"数据集摘要: {data_context['dataset_summary']}")
            if data_context.get("fields"):
                parts.append(f"数据字段: {', '.join(data_context['fields'])}")
            if data_context.get("statistics"):
                stats = data_context["statistics"]
                stat_lines = []
                if isinstance(stats, dict):
                    stat_lines.append(f"- 样本数: {stats.get('sample_count', 'N/A')}")
                    stat_lines.append(f"- 字段数: {stats.get('field_count', 'N/A')}")
                    stat_lines.append(f"- 缺失值比例: {stats.get('missing_rate', 'N/A')}")
                    if stats.get("field_distributions"):
                        stat_lines.append("- 字段分布:")
                        for fd in stats["field_distributions"]:
                            stat_lines.append(f"  {fd}")
                elif isinstance(stats, str):
                    stat_lines.append(stats)
                if stat_lines:
                    parts.append("初步统计:\n" + "\n".join(stat_lines))
            if data_context.get("preprocessing"):
                parts.append(f"预处理摘要: {data_context['preprocessing']}")

        if multimodal_datasets:
            parts.append("## 多模态数据集")
            for ds in multimodal_datasets:
                name = ds.get("name", ds.get("filename", "unknown"))
                modality = ds.get("modality", "unknown")
                fields = ds.get("fields", [])
                parts.append(f"- [{modality}] {name}")
                if fields:
                    parts.append(f"  字段: {', '.join(fields)}")

        if data_linking_evidence:
            parts.append("## 文献-数据关联证据")
            for ev in data_linking_evidence:
                fact_id = ev.get("fact_id", "?")
                field_ref = ev.get("field_ref", "?")
                relation = ev.get("relation", "")
                parts.append(f"- fact:{fact_id} → field:{field_ref}: {relation}")

        if not parts:
            return "（无项目数据上下文 — 假设必须基于文献事实或理论推测，evidence_level 建议为 low）"

        return "\n".join(parts)

    # ────────── 校验 ──────────

    def _validate_and_normalize_result(
        self,
        result_dict: Dict[str, Any],
        available_fact_ids: List[str],
        facts: List[Dict[str, Any]],
        research_question: str = "",
    ) -> HypothesisGenerationResult:
        """
        验证并标准化 LLM 输出：
          - ensuring supporting_fact_ids 只引用 real fact_ids
          - 自动标的 evidence_level
          - 偏题检测与标记
          - 确保 evidence 全空时降级 evidence_level
        """
        if "hypotheses" not in result_dict or not isinstance(result_dict["hypotheses"], list):
            result_dict["hypotheses"] = []

        fact_id_set = set(available_fact_ids)
        validated_hypotheses = []

        # 从研究问题中提取关键词用于偏题检测
        rq_lower = research_question.lower()

        for hypo in result_dict["hypotheses"]:
            if not isinstance(hypo, dict):
                continue

            # 确保所有必要字段存在
            for field in ["hypothesis", "rationale", "novelty", "testability",
                           "required_data", "possible_method", "risk"]:
                if field not in hypo:
                    hypo[field] = ""

            for field in ["question_alignment", "validation_target",
                           "expected_measurable_effect"]:
                if field not in hypo:
                    hypo[field] = ""

            for field in ["dataset_field_refs", "data_evidence_ids"]:
                if field not in hypo or not isinstance(hypo.get(field), list):
                    hypo[field] = []

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

            # ── 偏题检测 ──
            hypo_text = hypo.get("hypothesis", "")
            hypo_lower = hypo_text.lower()
            is_off_topic = False
            off_topic_reason = ""

            question_domains = self._detect_question_domain(research_question)

            # 1. 检查是否包含明显无关领域关键词（动态过滤：跳过研究问题所属领域的关键词）
            matched_off_domain = []
            for kw in self.OFF_DOMAIN_KEYWORDS:
                if kw.lower() in hypo_lower:
                    if self._is_keyword_in_domains(kw.lower(), question_domains):
                        continue
                    matched_off_domain.append(kw)

            # 2. 计算对齐分数
            rq_keywords = self._extract_topic_keywords(research_question) if research_question else set()
            hypo_keywords = self._extract_topic_keywords(hypo_text)
            overlap = rq_keywords & hypo_keywords if rq_keywords else set()

            # 对齐分数：基于关键词重叠度和领域匹配度
            if not rq_keywords:
                alignment_score = 50
            elif overlap:
                overlap_ratio = len(overlap) / max(len(rq_keywords), 1)
                alignment_score = int(30 + overlap_ratio * 70)
            else:
                alignment_score = max(5, len(hypo_keywords) * 2)

            if matched_off_domain:
                alignment_score = min(alignment_score, 20)

            # 3. 只有 alignment_score < 30 才标记为偏题
            if alignment_score < 30:
                is_off_topic = True
                if matched_off_domain:
                    off_topic_reason = f"假设内容涉及无关领域: {', '.join(matched_off_domain)}, alignment_score={alignment_score}"
                elif not overlap and rq_keywords:
                    off_topic_reason = f"假设关键词与研究问题关键词无交集, alignment_score={alignment_score}"
                else:
                    off_topic_reason = f"假设对齐度不足, alignment_score={alignment_score}"
                logger.warning(f"假设偏题检测命中: off_topic={is_off_topic}, score={alignment_score}, 假设: {hypo_text[:80]}")

            # 3. 如果 supporting_fact_ids、dataset_field_refs、data_evidence_ids 全为空 → evidence_level=low
            has_any_evidence = (
                bool(validated_ids)
                or bool(hypo.get("dataset_field_refs"))
                or bool(hypo.get("data_evidence_ids"))
            )
            if not has_any_evidence:
                hypo["evidence_level"] = "low"
                logger.info(f"假设无任何证据引用，强制 evidence_level=low: {hypo_text[:60]}...")
            else:
                # ── 自动标的 evidence_level ──
                hypo["evidence_level"] = self._determine_evidence_level(
                    raw_level=hypo.get("evidence_level", ""),
                    validated_ids=validated_ids,
                    facts_available=bool(available_fact_ids),
                )

            # 标记 off_topic
            hypo["off_topic"] = is_off_topic
            hypo["off_topic_reason"] = off_topic_reason
            hypo["alignment_score"] = alignment_score

            validated_hypotheses.append(HypothesisItem(**hypo))

        # ── 排序：非 off_topic 优先 ──
        validated_hypotheses.sort(key=lambda h: h.off_topic if hasattr(h, 'off_topic') and h.off_topic else False)

        # 限制 3-5 条
        if len(validated_hypotheses) > 5:
            logger.info(f"生成的假设数量超过 5 条，截断为 5 条")
            validated_hypotheses = validated_hypotheses[:5]

        result_dict["hypotheses"] = validated_hypotheses

        # 统计偏题
        off_topic_count = sum(1 for h in validated_hypotheses if hasattr(h, 'off_topic') and h.off_topic)
        if off_topic_count > 0:
            logger.warning(f"{off_topic_count}/{len(validated_hypotheses)} 条假设被标记为偏题")

        return HypothesisGenerationResult(**result_dict)

    @staticmethod
    def _extract_topic_keywords(text: str) -> set:
        """从文本中提取主题关键词（用于偏题检测）"""
        import re
        stopwords = {"的", "是", "在", "和", "了", "有", "中", "为", "与", "之",
                     "a", "an", "the", "of", "in", "to", "for", "and", "on", "is", "at"}
        # 提取中文词（2-4 字符）和英文词
        words = set()
        # 中文词
        chinese_chars = ''.join(re.findall(r'[\u4e00-\u9fff]+', text))
        for i in range(len(chinese_chars) - 1):
            for j in range(2, 5):
                if i + j <= len(chinese_chars):
                    w = chinese_chars[i:i + j]
                    if w not in stopwords:
                        words.add(w)
        # 英文词
        eng_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        for w in eng_words:
            if w not in stopwords:
                words.add(w)
        return words

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