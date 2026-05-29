"""
问题对齐 Skill (QuestionAlignmentSkill)
——检查生成的假设是否与用户研究问题对齐，过滤明显无关假设。
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

_OFF_DOMAIN_PATTERNS: List[str] = [
    r"肠道菌群",
    r"肠[道胃]微生物",
    r"gut\s*microbi[oa]",
    r"阿尔茨海默",
    r"alzheimer",
    r"帕金森",
    r"parkinson",
    r"SCFA",
    r"短链脂肪酸",
    r"短链[型]?脂肪[酸盐]",
    r"粪便[菌样]",
    r"粪[便样]",
    r"fecal",
    r"faeces",
    r"粪便",
    r"肠道[屏障壁]",
    r"肠[道壁]",
    r"大脑皮层",
    r"cerebral\s*cortex",
    r"海马体",
    r"hippocampus",
    r"神经退行",
    r"neurodegen",
    r"β.?淀粉样",
    r"amyloid\s*beta",
    r"tau\s*蛋白",
    r"tau\s*protein",
    r"小胶质细胞",
    r"microglia",
    r"炎症因子",
    r"inflammatory\s*cytokine",
    r"血脂屏障",
    r"blood[-\s]?brain\s*barrier",
    r"临?床[床治]疗",
    r"药[物理学]",
    r"随机对照",
    r"RCT",
    r"randomized\s*controlled\s*trial",
    r"抑郁症",
    r"depression",
    r"焦虑[症障]",
    r"anxiety",
    r"抗原",
    r"antigen",
    r"免疫细胞",
    r"immune\s*cell",
    r"T.?(细胞|淋巴细胞)",
    r"tumor",
    r"癌[症细胞]",
    r"cancer",
    r"肿瘤",
    r"肿瘤[免微]",
    r"oncology",
    r"基因编辑",
    r"CRISPR",
    r"genome\s*edit",
    r"干细胞",
    r"stem\s*cell",
    r"蛋白[质酶]",
    r"protein",
    r"酶[活催]",
    r"enzyme",
    r"DNA",
    r"RNA",
    r"核苷酸",
    r"nucleotide",
    r"细胞凋亡",
    r"apoptosis",
    r"信号通路",
    r"signaling\s*pathway",
    r"受体",
    r"receptor",
    r"临床[试验究]",
    r"clinical\s*trial",
    r"流行病",
    r"epidemiology",
    r"公共卫生",
    r"public\s*health",
    r"疫苗",
    r"vaccine",
    r"病毒[感]",
    r"virus",
    r"细菌",
    r"bacteria",
    r"社会经济",
    r"socioeconomic",
    r"教育干预",
    r"教育[公平策]",
    r"education",
    r"政治[体]",
    r"politics",
    r"政策[法]",
    r"policy",
    r"心理[健]",
    r"psychology",
]

_OFF_DOMAIN_COMPILED: List[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in _OFF_DOMAIN_PATTERNS]

_DOMAIN_CATEGORIES: Dict[str, Set[str]] = {
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
        "免疫细胞", "immune cell", "T细胞", "T淋巴细胞",
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

_ML_CS_CORE_KEYWORDS: Dict[str, List[str]] = {
    "method": [
        "CNN", "RNN", "LSTM", "GRU", "Transformer", "BERT", "GPT", "ResNet",
        "DenseNet", "EfficientNet", "GAN", "VAE", "AutoEncoder",
        "卷积神经网络", "循环神经网络", "残差网络", "注意力机制",
        "神经网络", "深度学习", "强化学习", "迁移学习", "对比学习",
        "自监督学习", "半监督学习", "集成学习", "决策树", "随机森林",
        "SVM", "XGBoost", "LightGBM", "KNN", "聚类", "降维",
        "特征提取", "特征选择", "数据增强", "正则化", "归一化",
        "fine.?tun", "transfer learning", "attention", "self.?attention",
        r"cross.?attention", "multi.?head", "backbone", "encoder",
        "decoder", "embedding", "tokeniz", "预训练", "pretrain",
        "联邦学习", "知识蒸馏", "剪枝", "量化", "轻量化",
    ],
    "task": [
        "分类", "回归", "检测", "分割", "识别", "预测", "推荐",
        "生成", "聚类", "异常检测", "目标检测", "行为检测",
        "行为识别", "动作识别", "意图识别", "姿态估计",
        "classification", "detection", "recognition", "prediction",
        "segmentation", "regression", "generation", "anomaly",
        "行为", "动作", "activity", "action", "gesture", "behavior",
    ],
    "metric": [
        "准确率", "精度", "召回率", "F1", "AUC", "AP", "mAP",
        "IoU", "BLEU", "ROUGE", "困惑度", "MSE", "MAE", "RMSE",
        "accuracy", "precision", "recall", "F1-score", "F1 score", "AUC",
        "ROC", "sensitivity", "specificity", "MCC",
    ],
    "data_domain": [
        "图像", "视频", "文本", "语音", "时序", "传感器",
        "image", "video", "text", "speech", "audio", "time.?series",
        "sensor", "multimodal", "多模态", "点云", "point cloud",
    ],
}


def _detect_question_domain(question: str) -> Set[str]:
    """从研究问题中检测所属领域类别"""
    lower_q = question.lower()
    domains: Set[str] = set()
    for domain, keywords in _DOMAIN_CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in lower_q:
                domains.add(domain)
                break
    return domains


def _extract_keywords_from_question(question: str) -> Dict[str, Set[str]]:
    """从研究问题中提取核心关键词"""
    keywords: Dict[str, Set[str]] = {
        "methods": set(),
        "tasks": set(),
        "metrics": set(),
        "domain": set(),
    }

    lower_q = question.lower()

    for cat, cat_key in [("methods", "method"), ("tasks", "task"), ("metrics", "metric"), ("domain", "data_domain")]:
        for kw in _ML_CS_CORE_KEYWORDS[cat_key]:
            if kw.lower() in lower_q:
                keywords[cat].add(kw)

    # 通用 NLP 提取：找中文/英文关键词短语
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,6}", question)
    for term in chinese_terms:
        for cat, cat_key in [("methods", "method"), ("tasks", "task"), ("metrics", "metric")]:
            for kw in _ML_CS_CORE_KEYWORDS[cat_key]:
                if term in kw or kw in term:
                    keywords[cat].add(kw)

    return keywords


def _compute_alignment(hypothesis: str, question_keywords: Dict[str, Set[str]], question_domains: Optional[Set[str]] = None) -> Dict[str, Any]:
    """计算单条假设的对齐度（基于研究问题领域动态过滤无关关键词）"""
    lower_h = hypothesis.lower()

    matched_methods = {kw for kw in question_keywords.get("methods", set()) if kw.lower() in lower_h}
    matched_tasks = {kw for kw in question_keywords.get("tasks", set()) if kw.lower() in lower_h}
    matched_metrics = {kw for kw in question_keywords.get("metrics", set()) if kw.lower() in lower_h}

    all_question_kw = set()
    for kws in question_keywords.values():
        all_question_kw.update(str(kw).lower() for kw in kws)

    matched_all = {kw for kw in all_question_kw if kw.lower() in lower_h}
    missing_all = all_question_kw - matched_all

    has_method = len(matched_methods) > 0
    has_task = len(matched_tasks) > 0
    has_metric = len(matched_metrics) > 0

    if not all_question_kw:
        score = 50
    elif has_method and has_task and has_metric:
        score = 85 + min(15, len(matched_all) * 3)
    elif (has_method or has_task) and has_metric:
        score = 70 + min(15, len(matched_all) * 3)
    elif has_method or has_task:
        score = 40 + min(30, len(matched_all) * 5)
    elif has_metric:
        score = 30 + min(20, len(matched_all) * 3)
    else:
        score = max(5, min(25, len(matched_all) * 5))

    score = min(100, score)

    question_domains = question_domains or set()

    off_topic = score < 30
    off_topic_reason = ""

    for pattern in _OFF_DOMAIN_COMPILED:
        match = pattern.search(hypothesis)
        if not match:
            continue
        match_text = match.group(0)
        matched_domain = _find_pattern_domain(pattern.pattern)
        if matched_domain and matched_domain in question_domains:
            continue
        off_topic = True
        score = min(score, 20)
        off_topic_reason = f"假设包含无关领域关键词: \"{match_text}\""
        break

    if not off_topic and score < 30:
        off_topic = True
        if missing_all:
            off_topic_reason = f"假设未覆盖研究问题的核心关键词，缺失: {', '.join(sorted(list(missing_all))[:5])}"
        else:
            off_topic_reason = "假设与研究问题的核心领域关联度不足"

    return {
        "alignment_score": score,
        "off_topic": off_topic,
        "off_topic_reason": off_topic_reason,
        "matched_keywords": sorted(list(matched_all)),
        "missing_keywords": sorted(list(missing_all)),
    }


def _find_pattern_domain(pattern_str: str) -> Optional[str]:
    """根据模式字符串查找所属领域类别"""
    pattern_lower = pattern_str.lower().replace(r"\s*", " ").replace(r"\s", " ").replace(r"\.", ".").replace(r"\?", "?")
    pattern_clean = re.sub(r"[\[\]\(\)\?\+\*\{\}]", "", pattern_lower).replace("\\", "").strip()
    for domain, keywords in _DOMAIN_CATEGORIES.items():
        for kw in keywords:
            kw_clean = kw.lower()
            if kw_clean in pattern_clean or pattern_clean in kw_clean:
                return domain
            if len(pattern_clean) >= 3 and pattern_clean[:3] in kw_clean:
                return domain
    return None


class QuestionAlignmentSkill(BaseSkill):
    """问题对齐 Skill

    输入:
      - research_question: str          研究问题
      - hypotheses: List[dict]           假设列表（每条含 hypothesis 字段或直接是字符串）

    输出 (SkillResult.data):
      - alignments: List[dict]           每条假设的对齐结果:
          - alignment_score: int          0-100
          - off_topic: bool               是否偏题
          - off_topic_reason: str         偏题原因
          - matched_keywords: List[str]   匹配到的关键词
          - missing_keywords: List[str]   缺失的关键词
      - all_off_topic: bool              是否所有假设都偏题
      - off_topic_summary: str            偏题汇总（供重新生成 Prompt 使用）
    """

    name = "QuestionAlignment"
    description = "检查生成的假设是否与用户研究问题对齐，过滤明显无关假设"
    source_reference = "AI Scientist — alignment / relevance verification 参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)

        research_question = input_data.get("research_question", "")
        hypotheses_raw = input_data.get("hypotheses", [])

        if not research_question:
            result.add_warning("research_question 为空，跳过对齐检查")
            result.data = {"alignments": [], "all_off_topic": False, "off_topic_summary": ""}
            return result

        if not hypotheses_raw:
            result.add_warning("hypotheses 为空，跳过对齐检查")
            result.data = {"alignments": [], "all_off_topic": False, "off_topic_summary": ""}
            return result

        question_keywords = _extract_keywords_from_question(research_question)
        question_domains = _detect_question_domain(research_question)
        logger.info(f"研究问题关键词: {question_keywords}, 所属领域: {question_domains}")

        alignments = []
        for h in hypotheses_raw:
            hypothesis_text = h.get("hypothesis", "") if isinstance(h, dict) else str(h)
            alignment = _compute_alignment(hypothesis_text, question_keywords, question_domains)
            alignment["hypothesis"] = hypothesis_text[:100]
            alignments.append(alignment)

        all_off_topic = all(a["off_topic"] for a in alignments)
        off_topic_summary = ""
        if all_off_topic:
            reasons = [a["off_topic_reason"] for a in alignments if a["off_topic_reason"]]
            off_topic_summary = "上一轮生成的假设全部偏题:\n" + "\n".join(
                f"- [{a.get('hypothesis', '?')[:60]}...] {a['off_topic_reason']}"
                for a in alignments
            )

        result.data = {
            "alignments": alignments,
            "all_off_topic": all_off_topic,
            "off_topic_summary": off_topic_summary,
        }

        logger.info(
            f"对齐检查完成: {len(alignments)} 条假设, "
            f"off_topic={sum(1 for a in alignments if a['off_topic'])}/{len(alignments)}, "
            f"all_off_topic={all_off_topic}"
        )

        return result