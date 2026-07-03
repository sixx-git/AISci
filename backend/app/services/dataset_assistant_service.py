"""数据集对话助手 — 解析自然语言并执行建模/预处理/质量分析等操作"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.research import Dataset
from app.services.dataset_service import DatasetService
from app.services.modeling_service import ModelingService
from app.services.qwen_client import get_qwen_client

logger = logging.getLogger(__name__)

MODELING_KEYWORDS = (
    "建模", "预测", "分类", "回归", "训练", "自动建模", "baseline",
    "model", "predict", "classif", "regress", "train",
)
PREPROCESS_KEYWORDS = ("预处理", "清洗", "清理", "preprocess", "clean", "标准化")
QUALITY_KEYWORDS = ("质量", "质量分析", "检查数据", "quality", "缺失率", "异常值", "outlier")


class DatasetAssistantService:
    def __init__(self, db: Session):
        self.db = db
        self.dataset_service = DatasetService(db)
        self.modeling_service = ModelingService(db)

    def _load_dataset(self, dataset_id: str) -> Optional[Dataset]:
        return self.db.query(Dataset).filter(Dataset.id == dataset_id).first()

    @staticmethod
    def _parse_columns(ds: Dataset) -> List[str]:
        if not ds.columns_json:
            return []
        try:
            cols = json.loads(ds.columns_json)
            return cols if isinstance(cols, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _mentioned_column(message: str, columns: List[str]) -> Optional[str]:
        for col in columns:
            if col in message or col.lower() in message.lower():
                return col
        return None

    def _rule_intent(self, message: str, columns: List[str]) -> Dict[str, Any]:
        msg = message.lower()
        target_column = self._mentioned_column(message, columns)

        if any(k in message or k in msg for k in MODELING_KEYWORDS):
            return {
                "action": "run_modeling",
                "target_column": target_column,
                "research_task": message.strip(),
                "reply": "",
            }
        if any(k in message or k in msg for k in PREPROCESS_KEYWORDS):
            return {"action": "preprocess", "reply": ""}
        if any(k in message or k in msg for k in QUALITY_KEYWORDS):
            return {"action": "quality_analysis", "reply": ""}

        return {"action": "answer_only", "reply": ""}

    def _llm_intent(
        self,
        message: str,
        ds: Dataset,
        columns: List[str],
        history: List[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        try:
            client = get_qwen_client()
            if not client.api_key:
                return None

            history_text = "\n".join(
                f"{h.get('role', 'user')}: {h.get('content', '')}" for h in history[-6:]
            )
            prompt = f"""你是科学数据助手。根据用户指令与数据集元信息，判断应执行的操作。

数据集: {ds.filename}
类型: {ds.data_type}
行数: {ds.n_rows or '未知'}
列数: {ds.n_columns or '未知'}
列名: {', '.join(columns[:30])}

对话历史:
{history_text or '（无）'}

用户最新消息:
{message}

返回 JSON，字段:
- action: run_modeling | preprocess | quality_analysis | answer_only
- target_column: 字符串或 null（仅当用户明确指定目标列时填写，须为上述列名之一）
- research_task: 字符串或 null（建模任务的自然语言描述）
- reply: 给用户的简短中文回复（answer_only 时必填；其他操作可留空由系统补充）
"""
            schema = {
                "action": "answer_only",
                "target_column": None,
                "research_task": None,
                "reply": "",
            }
            result = client.structured_chat(prompt, schema_example=schema, temperature=0.1)
            action = result.get("action", "answer_only")
            if action not in ("run_modeling", "preprocess", "quality_analysis", "answer_only"):
                action = "answer_only"
            target = result.get("target_column")
            if target and target not in columns:
                target = self._mentioned_column(str(target), columns)
            return {
                "action": action,
                "target_column": target,
                "research_task": result.get("research_task") or message.strip(),
                "reply": result.get("reply") or "",
            }
        except Exception as e:
            logger.warning("Dataset assistant LLM intent failed: %s", e)
            return None

    def _answer_only(
        self,
        message: str,
        ds: Dataset,
        columns: List[str],
        history: List[Dict[str, str]],
    ) -> str:
        try:
            client = get_qwen_client()
            if client.api_key:
                history_msgs = [
                    {"role": h.get("role", "user"), "content": h.get("content", "")}
                    for h in history[-8:]
                ]
                system = (
                    "你是 AISci 项目的数据集助手。根据数据集元信息回答用户问题，"
                    "可建议用户说「运行自动建模」「质量分析」「预处理」来执行操作。回答简洁、专业。"
                )
                user_ctx = (
                    f"数据集: {ds.filename}\n"
                    f"类型: {ds.data_type}, 行: {ds.n_rows}, 列: {ds.n_columns}\n"
                    f"列名: {', '.join(columns)}\n"
                    f"缺失率: {ds.missing_rate}\n\n"
                    f"用户问题: {message}"
                )
                messages = [{"role": "system", "content": system}, *history_msgs, {"role": "user", "content": user_ctx}]
                return client.chat_with_messages(messages, temperature=0.3)
        except Exception as e:
            logger.warning("Dataset assistant answer failed: %s", e)

        col_preview = ", ".join(columns[:8])
        if len(columns) > 8:
            col_preview += "…"
        return (
            f"「{ds.filename}」共 {ds.n_rows or '-'} 行、{ds.n_columns or '-'} 列。"
            f"字段包括：{col_preview or '暂无'}。"
            "你可以直接说：「运行自动建模」「做质量分析」或「预处理数据」。"
        )

    def _action_reply(self, action: str, success: bool, detail: str = "") -> str:
        labels = {
            "run_modeling": "自动建模",
            "preprocess": "数据预处理",
            "quality_analysis": "质量分析",
        }
        name = labels.get(action, action)
        if success:
            return f"{name}已完成。{detail}".strip()
        return f"{name}失败：{detail}".strip()

    async def chat(
        self,
        dataset_id: str,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        history = history or []
        ds = self._load_dataset(dataset_id)
        if not ds:
            return {
                "reply": "数据集不存在，请刷新后重试。",
                "action": "error",
                "action_success": False,
            }

        columns = self._parse_columns(ds)
        intent = self._rule_intent(message, columns)
        if intent["action"] == "answer_only":
            llm_intent = self._llm_intent(message, ds, columns, history)
            if llm_intent and llm_intent.get("action") != "answer_only":
                intent = llm_intent

        action = intent["action"]
        action_result: Optional[Dict[str, Any]] = None
        modeling_result: Optional[Dict[str, Any]] = None
        action_success = False
        reply = intent.get("reply") or ""

        if action == "run_modeling":
            if ds.data_type != "tabular":
                reply = "当前数据集不是表格类型，无法自动建模。请上传 CSV/Excel。"
            else:
                modeling_result = await self.modeling_service.run_modeling_pipeline(
                    dataset_id=dataset_id,
                    target_column=intent.get("target_column"),
                    research_task=intent.get("research_task") or message.strip(),
                )
                action_success = bool(modeling_result.get("success"))
                action_result = modeling_result
                if action_success:
                    detail = (
                        f"任务类型 {modeling_result.get('task_type')}，"
                        f"目标列 `{modeling_result.get('target_column')}`，"
                        f"最佳模型 {modeling_result.get('best_model')}。"
                    )
                    reply = reply or self._action_reply(action, True, detail)
                else:
                    reply = reply or self._action_reply(
                        action, False, modeling_result.get("error", "未知错误")
                    )

        elif action == "preprocess":
            updated = self.dataset_service.run_preprocessing(dataset_id)
            action_success = updated is not None
            action_result = {"preprocessing_status": updated.preprocessing_status if updated else None}
            reply = reply or self._action_reply(
                action,
                action_success,
                f"状态：{updated.preprocessing_status}" if updated else "数据集不存在",
            )

        elif action == "quality_analysis":
            action_result = self.dataset_service.run_single_quality_analysis(dataset_id)
            action_success = bool(action_result.get("success"))
            recs = (action_result.get("data") or {}).get("recommendations") or []
            detail = recs[0] if recs else ""
            reply = reply or self._action_reply(action, action_success, detail)

        else:
            reply = reply or self._answer_only(message, ds, columns, history)
            action = "answer_only"
            action_success = True

        return {
            "reply": reply,
            "action": action,
            "action_success": action_success,
            "action_result": action_result,
            "modeling_result": modeling_result if action == "run_modeling" else None,
        }
