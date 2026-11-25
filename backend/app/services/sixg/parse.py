"""自定义 6G 任务解析。推测数字必须带出来源，不能当成实测。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.services.sixg.topics import COORDINATOR_ROLE

ALLOWED_TOOLS = {
    "literature_pipeline": "复用原有七阶段文献、假设、评审和报告流程",
    "emergency_constraints": "仅当专题是空天地融合应急通信时，使用已实现的资源预检",
}

_SCHEMA = {
    "domain": "6G相关领域",
    "research_goal": "研究目标",
    "task_summary": "任务摘要",
    "constraints_text": "用户提出的约束",
    "applicable_tools": ["literature_pipeline"],
    "parameters": [
        {"name": "参数名", "value": "只有用户原文写出的值", "unit": "单位"}
    ],
    "missing_information": ["缺少的专业条件"],
}


def normalize_custom_parse(user_text: str, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """清洗模型输出。用户原文里出现的值记为用户提供，其余记为模型推测。"""
    data = raw if isinstance(raw, dict) else {}
    text = user_text or ""
    parameters: List[Dict[str, Any]] = []
    for item in data.get("parameters") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = item.get("value")
        value_text = "" if value is None else str(value).strip()
        if not name and not value_text:
            continue
        origin = "user_supplied" if value_text and value_text in text else "llm_inferred"
        parameters.append({
            "name": name or "未命名参数",
            "value": value_text,
            "unit": str(item.get("unit") or "").strip(),
            "origin": origin,
            "confirmed": False,
            "is_measured": False,
            "note": (
                "来自用户原文，尚未确认，也不是设备实测。"
                if origin == "user_supplied"
                else "大模型推测的数字，不是真实设备参数，确认前不得用于检查。"
            ),
        })
    tools = []
    for tool_id in data.get("applicable_tools") or []:
        if tool_id in ALLOWED_TOOLS and tool_id not in tools:
            tools.append(tool_id)
    if "literature_pipeline" not in tools:
        tools.insert(0, "literature_pipeline")
    return {
        "domain": str(data.get("domain") or "").strip() or "6G",
        "research_goal": str(data.get("research_goal") or "").strip(),
        "task_summary": str(data.get("task_summary") or "").strip(),
        "constraints_text": str(data.get("constraints_text") or "").strip(),
        "parameters": parameters,
        "applicable_tools": tools,
        "tool_notes": {key: ALLOWED_TOOLS[key] for key in tools},
        "missing_information": [
            str(item).strip() for item in (data.get("missing_information") or []) if str(item).strip()
        ],
        "verification_status": "待专业验证",
        "verification_note": "自定义任务没有默认的专业检查器。解析结果不能代替仿真或实测。",
        "coordinator_role": COORDINATOR_ROLE,
        "parser": "qwen_structured",
    }


def parse_custom_task(user_text: str, llm_call: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    text = (user_text or "").strip()
    if not text:
        raise ValueError("请先填写自定义 6G 任务")
    caller = llm_call or _default_llm
    prompt = (
        "请把下面的 6G 研究或应用任务解析为 JSON。"
        "只提取用户明确写出的参数，不要补充带宽、时延、功率、终端数等未给出的数字。"
        "applicable_tools 只能从 literature_pipeline 与 emergency_constraints 中选择。\n\n"
        f"用户任务：\n{text}"
    )
    try:
        raw = caller(
            prompt=prompt,
            schema_example=_SCHEMA,
            temperature=0.1,
            prompt_version="sixg_custom_parse",
        )
    except Exception:
        raw = {
            "domain": "6G",
            "research_goal": "",
            "task_summary": text[:500],
            "applicable_tools": ["literature_pipeline"],
            "parameters": [],
            "missing_information": ["自动解析失败，请手工填写领域、目标和约束。"],
        }
    parsed = normalize_custom_parse(text, raw if isinstance(raw, dict) else {})
    if not parsed["task_summary"]:
        parsed["task_summary"] = text[:500]
    return parsed


def _default_llm(**kwargs: Any) -> Dict[str, Any]:
    from app.services.qwen_client import qwen_structured_chat

    return qwen_structured_chat(**kwargs)
