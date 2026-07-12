"""Skill 注册表 — 发现、分类、启用状态管理"""
from __future__ import annotations

import importlib
import inspect
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

_RUNTIME_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "skill_runtime.json"

CATEGORY_LABELS: Dict[str, str] = {
    "literature": "文献",
    "reasoning": "推理",
    "experiment": "实验",
    "data": "数据",
    "report": "报告",
    "modeling": "建模",
    "data_finder": "数据查找",
    "federated_experiment": "联邦实验",
    "multimodal": "多模态",
    "evidence_reasoning": "证据推理",
    "chinese_writing": "中文写作",
    "impact_prediction": "影响力预测",
    "general": "通用",
}

# skill.name -> 使用该 Skill 的智能体 / 服务
CONSUMER_SKILL_MAP: Dict[str, List[str]] = {
    "文献挖掘 Agent": [
        "SearchPapers", "PaperFullTextRAG", "LiteratureEvidenceRetrieval",
        "PdfEvidenceExtraction", "ArxivSearch", "ClaimExtraction",
        "CitationGrounding", "MultimodalDataLinking",
    ],
    "假设评审 Agent": ["HypothesisNoveltyReview", "HypothesisTournament"],
    "实验设计 Agent": [
        "ExperimentSanityCheck", "ExperimentPlanCritic", "TaskDecomposition",
        "ExperimentProtocol", "MultimodalDataIngest",
        "MultimodalDataLinking", "DatasetDiscovery",
    ],
    "小样验证 Agent": [
        "PreliminaryAnalysis", "ResultVerification",
        "SimulationExecutor", "ResultAnalyzer", "LabNotebook",
    ],
    "报告生成 Agent": [
        "CitationGrounding", "CitationIntegrityCheck", "ReportChartGeneration",
        "ScientificPlot", "ReportQualityCheck", "ProposalLogicReview", "ReportReviewer",
        "ChineseStyleDiagnosis", "HumanizeRewrite", "ToneControl",
        "ReportInfluencePrediction",
    ],
    "Pipeline 编排": [
        "QuestionAlignment", "IdeationNovelty", "IterativeHypothesisLoop",
        "TaskDecomposition", "Replanning",
        "CounterfactualPreview",
    ],
    "数据建模服务": [
        "DatasetProfiling", "DataCleaningPlan", "FeatureEngineering",
        "TaskTypeDetection", "DataPreprocessing",
        "BaselineModelTraining", "BaselineTraining",
        "ModelEvaluation", "ErrorAnalysis", "SelfCorrection", "ExperimentTracking",
    ],
    "数据集服务": ["data_juicer_lite"],
    "多源数据查找": [
        "DataRequirementUnderstanding", "ScientificDataSearch", "PaperDataLinkExtractor",
        "TextFactsExtraction", "ExternalDatasetSearch",
        "FigureDataExtraction", "FigureVlmSeries", "PdfFigureCrop",
        "TableExtraction", "PdfTableExtraction",
        "SupplementaryFetch", "SupplementaryExtraction",
        "DataProvenance", "DatasetSchemaAlignment", "DatasetMerge", "EntityResolution",
        "TabularFileExtraction", "ChemStructureExtraction", "StructuredFileExtraction",
    ],
    "联邦实验服务": [
        "FederatedDataSchema", "FederatedExperimentPlan", "PrivacyMechanismSuggestion",
        "FederatedSimulationExecutor", "FederatedResultAnalysis", "FederatedReplanning",
        "FederatedScenarioRecognition", "FederatedBaselineSelection", "FederatedRuntimeExecutor",
    ],
    "多模态服务": [
        "QwenVlImageUnderstanding", "AudioTranscription", "MultimodalEvidenceBuilder",
    ],
    "证据推理服务": [
        "EvidenceRetrieval", "LiteratureEvidenceRetrieval", "EvidenceGrounding",
        "EvidenceChainBuilder", "EvidenceStanceClassification",
        "ScientificClaimExtraction", "ClaimExtraction",
        "CitationIntegrityCheck", "CounterEvidenceRetrieval", "CounterEvidenceSearch",
        "HypothesisRevision", "HypothesisRefinement", "MechanismReasoning",
    ],
    "人在回路": ["MentorReview"],
    "中文写作服务": [
        "ChineseStyleDiagnosis", "HumanizeRewrite", "RevisionReason",
        "MultiVersionRewrite", "ChineseGECCheck", "ToneControl",
    ],
    "影响力预测服务": [
        "PaperFeatureExtraction", "CitationGraphFeature", "EarlyImpactPrediction",
        "BiasExplanation", "ImpactCalibration", "ReportInfluencePrediction",
    ],
    "图表质量": ["PlotVlmCritique", "ScientificPlot"],
}

# Pipeline 九阶段正常运行所依赖的核心 Skill（不可禁用）
REQUIRED_SKILL_IDS: frozenset[str] = frozenset({
    # Pipeline 编排
    "QuestionAlignment",
    # 文献挖掘 / 引用
    "PdfEvidenceExtraction",
    "SearchPapers",
    "MultimodalDataLinking",
    "CitationGrounding",
    # 证据推理链
    "IterativeHypothesisLoop",
    "ScientificClaimExtraction",
    "EvidenceRetrieval",
    "CounterEvidenceRetrieval",
    "EvidenceStanceClassification",
    "HypothesisRevision",
    "EvidenceChainBuilder",
    "CitationIntegrityCheck",
    # 多源数据采集
    "DataRequirementUnderstanding",
    "PaperDataLinkExtractor",
    "TextFactsExtraction",
    "ExternalDatasetSearch",
    "FigureDataExtraction",
    "FigureVlmSeries",
    "PdfFigureCrop",
    "SupplementaryFetch",
    "SupplementaryExtraction",
    "PdfTableExtraction",
    "DataProvenance",
    "DatasetSchemaAlignment",
    "DatasetMerge",
    "EntityResolution",
    "TabularFileExtraction",
    "ChemStructureExtraction",
    "StructuredFileExtraction",
    # 假设评审
    "HypothesisNoveltyReview",
    "MentorReview",
    # 实验设计
    "ExperimentSanityCheck",
    "MultimodalDataIngest",
    "DatasetDiscovery",
    # 小样验证
    "PreliminaryAnalysis",
    # 报告生成
    "ReportChartGeneration",
    "ScientificPlot",
    "ReportQualityCheck",
})


class SkillToggleError(Exception):
    """尝试修改锁定 Skill 的启用状态时抛出。"""

    def __init__(self, skill_id: str, message: str):
        self.skill_id = skill_id
        super().__init__(message)


@dataclass
class SkillRecord:
    id: str
    name: str
    description: str
    category: str
    category_label: str
    module_path: str
    agents: List[str]
    enabled: bool
    locked: bool = False
    source_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_discovered_cache: Optional[List[SkillRecord]] = None


def _consumers_for_skill(skill_name: str) -> List[str]:
    agents: List[str] = []
    for agent, skills in CONSUMER_SKILL_MAP.items():
        if skill_name in skills:
            agents.append(agent)
    return agents


def _category_from_module(module_path: str) -> str:
    parts = module_path.split(".")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "skills":
        cat = parts[2]
        if cat != "skills" and not cat.endswith("_skill"):
            return cat
    return "general"


def _load_runtime() -> Dict[str, Any]:
    if not _RUNTIME_FILE.exists():
        return {"disabled": []}
    try:
        with open(_RUNTIME_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"disabled": []}
        disabled = data.get("disabled", [])
        return {"disabled": disabled if isinstance(disabled, list) else []}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("读取 skill_runtime.json 失败: %s", e)
        return {"disabled": []}


def _save_runtime(data: Dict[str, Any]) -> None:
    _RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_RUNTIME_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_skill_locked(skill_id: str) -> bool:
    return skill_id in REQUIRED_SKILL_IDS


def _sanitize_runtime_disabled() -> None:
    """从持久化配置中移除被锁定的 Skill，防止历史误禁用。"""
    runtime = _load_runtime()
    disabled = set(runtime.get("disabled", []))
    cleaned = disabled - REQUIRED_SKILL_IDS
    if cleaned != disabled:
        runtime["disabled"] = sorted(cleaned)
        _save_runtime(runtime)


def _apply_record_state(record: SkillRecord, disabled: set[str]) -> SkillRecord:
    locked = is_skill_locked(record.id)
    enabled = True if locked else record.id not in disabled
    return SkillRecord(**{**record.to_dict(), "locked": locked, "enabled": enabled})


def is_skill_enabled(skill_id: str) -> bool:
    if is_skill_locked(skill_id):
        return True
    disabled = set(_load_runtime().get("disabled", []))
    return skill_id not in disabled


def discover_skills(refresh: bool = False) -> List[SkillRecord]:
    global _discovered_cache
    _sanitize_runtime_disabled()
    runtime = _load_runtime()
    disabled = set(runtime.get("disabled", []))

    if _discovered_cache is not None and not refresh:
        return [_apply_record_state(s, disabled) for s in _discovered_cache]

    skills_root = Path(__file__).resolve().parent.parent / "skills"
    found: Dict[str, SkillRecord] = {}

    skill_files = sorted(set(skills_root.rglob("*_skill.py")) | set(skills_root.rglob("*_skills.py")))
    for py_file in skill_files:
        if py_file.name.startswith("_"):
            continue
        rel = py_file.relative_to(skills_root).with_suffix("")
        module_path = "app.skills." + ".".join(rel.parts)
        try:
            mod = importlib.import_module(module_path)
        except Exception as e:
            logger.warning("无法加载 Skill 模块 %s: %s", module_path, e)
            continue

        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if not issubclass(cls, BaseSkill) or cls is BaseSkill:
                continue
            skill_name = getattr(cls, "name", "") or cls.__name__
            if not skill_name or skill_name in found:
                continue
            category = _category_from_module(module_path)
            locked = is_skill_locked(skill_name)
            record = SkillRecord(
                id=skill_name,
                name=skill_name,
                description=(getattr(cls, "description", "") or "").strip(),
                category=category,
                category_label=CATEGORY_LABELS.get(category, category),
                module_path=module_path,
                agents=_consumers_for_skill(skill_name),
                enabled=True if locked else skill_name not in disabled,
                locked=locked,
                source_reference=getattr(cls, "source_reference", None),
            )
            found[skill_name] = record

    _discovered_cache = sorted(found.values(), key=lambda s: (s.category, s.name))
    return [_apply_record_state(s, disabled) for s in _discovered_cache]


def list_skills(
    category: Optional[str] = None,
    agent: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[Dict[str, Any]]:
    items = discover_skills()
    if category:
        items = [s for s in items if s.category == category]
    if agent:
        items = [s for s in items if agent in s.agents]
    if keyword:
        kw = keyword.lower()
        items = [
            s for s in items
            if kw in s.name.lower()
            or kw in s.description.lower()
            or kw in s.category_label.lower()
        ]
    return [s.to_dict() for s in items]


def list_agents() -> List[Dict[str, Any]]:
    skills = discover_skills()
    by_name = {s.id: s for s in skills}
    result: List[Dict[str, Any]] = []
    for agent, skill_names in CONSUMER_SKILL_MAP.items():
        bound = [by_name[n].to_dict() for n in skill_names if n in by_name]
        result.append({
            "agent": agent,
            "skill_count": len(bound),
            "skills": [s["id"] for s in bound],
        })
    return result


def set_skill_enabled(skill_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    skills = discover_skills()
    target = next((s for s in skills if s.id == skill_id), None)
    if not target:
        return None

    if target.locked:
        raise SkillToggleError(
            skill_id,
            f"Skill「{skill_id}」为 Pipeline 核心能力，不可更改启用状态",
        )

    runtime = _load_runtime()
    disabled = set(runtime.get("disabled", []))
    if enabled:
        disabled.discard(skill_id)
    else:
        disabled.add(skill_id)
    runtime["disabled"] = sorted(disabled - REQUIRED_SKILL_IDS)
    _save_runtime(runtime)

    global _discovered_cache
    disabled = set(runtime.get("disabled", []))
    if _discovered_cache:
        _discovered_cache = [_apply_record_state(s, disabled) for s in _discovered_cache]

    updated = next((s for s in discover_skills() if s.id == skill_id), None)
    return updated.to_dict() if updated else None


def get_summary() -> Dict[str, Any]:
    skills = discover_skills()
    enabled_count = sum(1 for s in skills if s.enabled)
    locked_count = sum(1 for s in skills if s.locked)
    categories = sorted({s.category for s in skills})
    return {
        "total": len(skills),
        "enabled": enabled_count,
        "disabled": len(skills) - enabled_count,
        "locked": locked_count,
        "categories": [
            {
                "id": c,
                "label": CATEGORY_LABELS.get(c, c),
                "count": sum(1 for s in skills if s.category == c),
            }
            for c in categories
        ],
        "agents": list(CONSUMER_SKILL_MAP.keys()),
    }
