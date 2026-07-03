"""数据集对话助手意图解析测试"""
from app.services.dataset_assistant_service import DatasetAssistantService


def test_rule_intent_modeling():
    svc = DatasetAssistantService(db=None)  # type: ignore[arg-type]
    columns = ["record_id", "model_type", "accuracy"]
    intent = svc._rule_intent("请用 model_type 做分类预测并自动建模", columns)
    assert intent["action"] == "run_modeling"
    assert intent["target_column"] == "model_type"


def test_rule_intent_quality():
    svc = DatasetAssistantService(db=None)  # type: ignore[arg-type]
    intent = svc._rule_intent("检查一下数据质量", [])
    assert intent["action"] == "quality_analysis"


def test_rule_intent_preprocess():
    svc = DatasetAssistantService(db=None)  # type: ignore[arg-type]
    intent = svc._rule_intent("先预处理清洗数据", [])
    assert intent["action"] == "preprocess"
