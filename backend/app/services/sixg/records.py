"""把 6G 专题和已有预检记录写成报告附录。数字只来自已保存的运行结果。"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.project_modes import is_emergency_6g_mode
from app.models.project import Project, Report
from app.services.sixg.topics import COORDINATOR_ROLE, get_topic, topic_id_from_config

_STATUS_ZH = {
    "pass": "预检通过（仅限已实现的资源约束）",
    "fail": "预检未通过",
    "partial": "部分问题已解决、整体方案仍不满足条件",
}


def render_sixg_appendix(project: Project) -> str:
    config = project.config or {}
    topic = get_topic(topic_id_from_config(config))
    app = config.get("sixg_app") or {}
    lines: List[str] = [
        "## 6G专题运行记录",
        "",
        f"- 专题：{topic['label']}",
        f"- 执行方式：{'完整科研分析' if app.get('execution_mode') == 'full' else '快速方案预检'}",
        f"- 专业检查：{topic['verification_status']}",
        f"- 说明：{app.get('verification_note') or topic['verification_note']}",
        f"- 大家长：{COORDINATOR_ROLE}",
        "",
    ]
    if topic["verification_status"] != "deterministic":
        lines.extend([
            "本专题当前没有专用确定性检查工具，专业指标状态为待专业验证。",
            "报告不包含由大模型生成的仿真、覆盖或时延结果。",
            "",
        ])
    custom = app.get("custom_parse")
    if isinstance(custom, dict) and custom.get("parameters"):
        lines.append("### 用户任务参数（非设备实测）")
        lines.append("")
        for item in custom["parameters"]:
            origin = "用户原文" if item.get("origin") == "user_supplied" else "模型推测"
            confirmed = "已核对" if item.get("confirmed") else "未核对"
            lines.append(
                f"- {item.get('name')}：{item.get('value')} {item.get('unit') or ''}（{origin}，{confirmed}，不是实测）"
            )
        lines.append("")
    state = config.get("emergency_comm")
    versions = state.get("versions") if isinstance(state, dict) else None
    if topic["id"] == "emergency_comm" and versions:
        lines.extend(["### 应急通信确定性预检", ""])
        lines.append(state.get("disclaimer") or "")
        lines.append("")
        for version in versions:
            check = version.get("check") or {}
            plan = version.get("plan") or {}
            lines.append(
                f"- 版本 {version.get('version')}｜{_STATUS_ZH.get(version.get('status'), version.get('status'))}"
            )
            lines.append(
                f"  需求 {check.get('demand_mbps')} Mbps，可用回传 {check.get('backhaul_mbps')} Mbps，"
                f"保障终端 {plan.get('serve_terminal_count')}，无人机连续 {plan.get('uav_continuous_min')} 分钟。"
            )
            failed = "、".join(check.get("failed_ids") or []) or "无"
            lines.append(f"  未通过项：{failed}。检查引擎：{check.get('engine')}。")
            coordinator = version.get("coordinator") or {}
            if coordinator.get("message"):
                lines.append(f"  大家长记录：{coordinator.get('message')}")
        lines.append("")
    elif topic["id"] == "emergency_comm":
        lines.append("尚未产生应急通信预检版本。")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def append_sixg_to_report_dict(db: Session, project_id: str, result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """完整科研报告生成后附加已有 6G 记录。附加失败不阻断原报告。"""
    if not project_id or not isinstance(result_dict, dict):
        return result_dict
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not is_emergency_6g_mode(getattr(project, "project_mode", None)):
            return result_dict
        appendix = render_sixg_appendix(project)
        markdown = result_dict.get("markdown_content") or ""
        result_dict["markdown_content"] = f"{markdown}\n\n{appendix}".strip()
        chapters = result_dict.get("chapters")
        if isinstance(chapters, dict):
            previous = chapters.get("results") or ""
            chapters["results"] = f"{previous}\n\n{appendix}".strip()
        result_dict["sixg_appendix_included"] = True
    except Exception:
        return result_dict
    return result_dict


def save_precheck_report(db: Session, project: Project) -> Report:
    topic = get_topic(topic_id_from_config(project.config))
    appendix = render_sixg_appendix(project)
    question = project.research_question or topic["research_question"] or topic["label"]
    title = f"{topic['label']}运行记录"
    report = Report(
        project_id=project.id,
        title=title,
        paper_title=title,
        paper_abstract=appendix[:1000],
        markdown_content=appendix,
        problem_statement=question,
        rationale=topic["research_background"] or "本记录只汇总项目内已保存的专题说明和程序检查。",
        technical_details=(
            "应急通信约束由 deterministic_rules_v1 计算。"
            "其他 6G 专题在缺少工具时标记为待专业验证。"
            "大家长只保存协调记录。"
        ),
        datasets="未使用外部数据集。应急通信数字来自用户设定的模拟场景。",
        source="project.config.sixg_app 与 project.config.emergency_comm",
        target=topic["expected_output"],
        methods="预定义专题模板、可选的自定义任务解析，以及已实现的确定性预检。",
        experiments=appendix,
        results=appendix,
        references="本记录不新增文献引用。文献事实仅来自完整科研流程中已绑定来源的 Fact。",
        status="ready",
        generated_by="sixg_precheck_record",
        model_used="deterministic_rules_v1" if topic["tool"] else "none",
        extra_metadata={
            "sixg_topic": topic["id"],
            "verification_status": topic["verification_status"],
            "llm_simulation": False,
        },
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
