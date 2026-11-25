"""把 6G 专题写入项目，并保留原有科研字段。"""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm.attributes import flag_modified

from app.models.project import Project
from app.services.sixg.topics import COORDINATOR_ROLE, EMERGENCY_TOPIC, get_topic, public_topic


def apply_sixg_profile(
    project: Project,
    *,
    topic_id: str | None,
    execution_mode: str | None,
    user_question: str | None = None,
) -> Dict[str, Any]:
    topic = get_topic(topic_id)
    execution = execution_mode if execution_mode in {"quick", "full"} else "quick"
    question = (user_question or "").strip()
    if topic["id"] == "custom":
        if question:
            project.research_question = question
    elif not (project.research_question or "").strip():
        project.research_question = question or topic["research_question"]
    if not (project.research_domain or "").strip():
        project.research_domain = topic["domain"]
    if not (project.research_goal or "").strip():
        project.research_goal = topic["research_goal"]
    if not (project.research_background or "").strip():
        project.research_background = topic["research_background"]
    if not (project.constraints or "").strip():
        project.constraints = topic["constraints"]
    if not (project.expected_output or "").strip():
        project.expected_output = topic["expected_output"]
    if not (project.keywords or "").strip():
        project.keywords = topic["keywords"]
    config = dict(project.config or {})
    config["sixg_app"] = {
        "topic_id": topic["id"],
        "execution_mode": execution,
        "verification_status": topic["verification_status"],
        "verification_note": topic["verification_note"],
        "tool": topic["tool"],
        "coordinator_role": COORDINATOR_ROLE,
        "custom_parse": None,
    }
    project.config = config
    flag_modified(project, "config")
    return public_profile(project)


def public_profile(project: Project) -> Dict[str, Any]:
    config = project.config or {}
    app = dict(config.get("sixg_app") or {})
    topic = get_topic(app.get("topic_id") or EMERGENCY_TOPIC)
    if not app:
        app = {
            "topic_id": topic["id"],
            "execution_mode": "quick",
            "verification_status": topic["verification_status"],
            "verification_note": topic["verification_note"],
            "tool": topic["tool"],
            "coordinator_role": COORDINATOR_ROLE,
            "custom_parse": None,
        }
    emergency_enabled = topic["id"] == EMERGENCY_TOPIC and topic["tool"] == "emergency_constraints"
    return {
        "topic": public_topic(topic),
        "execution_mode": app.get("execution_mode") or "quick",
        "verification_status": topic["verification_status"],
        "verification_note": app.get("verification_note") or topic["verification_note"],
        "coordinator_role": COORDINATOR_ROLE,
        "custom_parse": app.get("custom_parse"),
        "emergency_tool_enabled": emergency_enabled,
        "research_question": project.research_question,
    }


def save_custom_parse(project: Project, parsed: Dict[str, Any]) -> None:
    config = dict(project.config or {})
    app = dict(config.get("sixg_app") or {})
    app["topic_id"] = "custom"
    app["custom_parse"] = parsed
    app["verification_status"] = "待专业验证"
    app["verification_note"] = parsed.get("verification_note")
    app["tool"] = None
    config["sixg_app"] = app
    project.config = config
    flag_modified(project, "config")
    if parsed.get("domain") and not (project.research_domain or "").strip():
        project.research_domain = parsed["domain"]
    if parsed.get("research_goal") and not (project.research_goal or "").strip():
        project.research_goal = parsed["research_goal"]


def confirm_custom_parameters(project: Project, parameters: list) -> Dict[str, Any]:
    config = dict(project.config or {})
    app = dict(config.get("sixg_app") or {})
    parsed = dict(app.get("custom_parse") or {})
    existing = {item.get("name"): item for item in parsed.get("parameters") or []}
    updated = []
    for item in parameters:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        previous = dict(existing.get(name) or {})
        value = item.get("value", previous.get("value"))
        value_text = "" if value is None else str(value).strip()
        updated.append({
            "name": name or previous.get("name") or "未命名参数",
            "value": value_text,
            "unit": str(item.get("unit") or previous.get("unit") or ""),
            "origin": previous.get("origin") or "user_supplied",
            "confirmed": bool(item.get("confirmed")),
            "is_measured": False,
            "note": "用户已核对的任务参数，仍然不是设备实测。",
        })
    parsed["parameters"] = updated
    parsed["verification_status"] = "待专业验证"
    app["custom_parse"] = parsed
    app["verification_status"] = "待专业验证"
    config["sixg_app"] = app
    project.config = config
    flag_modified(project, "config")
    return parsed
