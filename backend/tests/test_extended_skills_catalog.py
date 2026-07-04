"""扩展 Skill 目录注册测试"""
import asyncio

from app.services.skill_registry_service import discover_skills

CATALOG_IDS = {
    # 建模
    "DatasetProfiling", "DataCleaningPlan", "FeatureEngineering",
    "BaselineTraining", "ModelEvaluation", "ErrorAnalysis",
    "SelfCorrection", "ExperimentTracking",
    # 证据
    "LiteratureEvidenceRetrieval", "ClaimExtraction", "EvidenceChainBuilder",
    "CounterEvidenceSearch", "HypothesisRefinement", "CitationGrounding",
    "MechanismReasoning",
    # 实验
    "TaskDecomposition", "ExperimentProtocol", "SimulationExecutor",
    "ResultAnalyzer", "Replanning", "LabNotebook",
    # 数据
    "ScientificDataSearch", "PaperDataLinkExtractor", "TableExtraction",
    "FigureDataExtraction", "DatasetSchemaAlignment", "DataProvenance", "DatasetMerge",
    # 中文写作
    "ChineseStyleDiagnosis", "HumanizeRewrite", "RevisionReason",
    "MultiVersionRewrite", "ChineseGECCheck", "ToneControl",
    # 影响力
    "PaperFeatureExtraction", "CitationGraphFeature", "EarlyImpactPrediction",
    "BiasExplanation", "ImpactCalibration", "ReportInfluencePrediction",
}


def test_extended_catalog_registered():
    skills = discover_skills(refresh=True)
    by_id = {s.id: s for s in skills}
    missing = [sid for sid in CATALOG_IDS if sid not in by_id]
    assert not missing, f"未注册: {missing}"


def test_data_cleaning_plan_from_profile():
    from app.skills.modeling.modeling_extension_skills import DataCleaningPlanSkill

    skill = DataCleaningPlanSkill()
    result = asyncio.run(skill.run(
        {"profile": {"missing_rate": 0.25, "outlier_hints": ["列 a 异常"], "numeric_stats": {}}},
        {},
    ))
    assert result.success
    assert result.data["step_count"] >= 1


def test_chinese_style_diagnosis():
    from app.skills.chinese_writing.chinese_writing_skills import ChineseStyleDiagnosisSkill

    skill = ChineseStyleDiagnosisSkill()
    result = asyncio.run(skill.run(
        {"text": "综上所述，在当今人工智能时代，赋能科研创新。"},
        {},
    ))
    assert result.success
    assert result.data["ai_flavor_risk"] in ("high", "medium", "low")
