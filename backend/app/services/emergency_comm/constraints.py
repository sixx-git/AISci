"""
应急通信资源约束预检。

只根据用户给定的模拟场景参数做算术和规则判断。
不调用大模型，不把场景参数写成文献 Fact。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple


ENGINE_ID = "deterministic_rules_v1"

DISCLAIMER = (
    "通过资源约束预检不代表真实无线覆盖、吞吐量、端到端时延或部署安全已经验证。"
    "场景参数是人为设定的模拟条件，不是文献 Fact，也不是设备实测值。"
)

PARTIAL_SUMMARY = "部分问题已解决、整体方案仍不满足条件"

_PATCH_KEYS = {
    "coverage",
    "serve_terminal_count",
    "mbps_per_terminal",
    "service_requirement_changed",
    "uses_uav_relay",
    "uav_used",
    "uav_continuous_min",
    "change_note",
}


def demo_scenario() -> Dict[str, Any]:
    """比赛演示用例。数字均为模拟条件。"""
    return {
        "location": "虚拟近海岛屿",
        "disaster": "台风导致部分地面通信设施失效",
        "networks": ["剩余地面网络", "无人机中继", "卫星回传"],
        "terminals": 30,
        "priority_terminals": 10,
        "demand_mbps_per_terminal": 1.0,
        "satellite_backhaul_mbps": 20.0,
        "ground_backhaul_mbps": 0.0,
        "uav_count": 1,
        "uav_endurance_min": 60,
        "mission_duration_min": 90,
        "parameter_origin": "simulated_user_input",
    }


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def available_backhaul_mbps(scenario: Dict[str, Any]) -> float:
    return _num(scenario.get("satellite_backhaul_mbps")) + _num(scenario.get("ground_backhaul_mbps"))


def validate_scenario(scenario: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not str(scenario.get("location") or "").strip():
        errors.append("缺少应用地点")
    if not str(scenario.get("disaster") or "").strip():
        errors.append("缺少灾害类型")
    terminals = scenario.get("terminals")
    priority = scenario.get("priority_terminals")
    if not isinstance(terminals, (int, float)) or int(terminals) < 1:
        errors.append("通信终端数量必须是不小于 1 的数字")
    elif not isinstance(priority, (int, float)) or int(priority) < 0:
        errors.append("救援优先终端数量必须是不小于 0 的数字")
    elif int(priority) > int(terminals):
        errors.append("救援优先终端数量不能超过通信终端总数")
    if _num(scenario.get("demand_mbps_per_terminal"), -1) <= 0:
        errors.append("单终端业务需求必须大于 0")
    if _num(scenario.get("satellite_backhaul_mbps"), -1) < 0:
        errors.append("卫星回传容量不能为负数")
    if _num(scenario.get("ground_backhaul_mbps"), -1) < 0:
        errors.append("地面剩余回传容量不能为负数")
    if not isinstance(scenario.get("uav_count"), (int, float)) or int(scenario.get("uav_count")) < 0:
        errors.append("无人机数量必须是不小于 0 的数字")
    if _num(scenario.get("uav_endurance_min"), -1) < 0:
        errors.append("无人机续航不能为负数")
    if _num(scenario.get("mission_duration_min"), 0) < 1:
        errors.append("保障任务时长必须不小于 1 分钟")
    return errors


def build_initial_plan(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """按场景原样生成第一版候选方案：同时保障全部终端，无人机飞满任务时长。"""
    uav_count = int(_num(scenario.get("uav_count")))
    uses_uav = uav_count > 0
    mission = int(_num(scenario.get("mission_duration_min")))
    return {
        "coverage": "all_terminals",
        "serve_terminal_count": int(_num(scenario.get("terminals"))),
        "mbps_per_terminal": _num(scenario.get("demand_mbps_per_terminal")),
        "uses_uav_relay": uses_uav,
        "uav_used": 1 if uses_uav else 0,
        "uav_continuous_min": mission if uses_uav else 0,
        "uses_satellite_backhaul": True,
        "service_requirement_changed": False,
        "change_note": "",
        "source": "structured_template",
        "source_note": "由场景参数结构化生成，不是文献 Fact，也不是实测通信指标。",
    }


def adapt_plan_to_scenario(plan: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
    """场景数字变化后，保持已确认的保障范围，按新参数重算需求与续航。"""
    coverage = plan.get("coverage") or "all_terminals"
    if coverage == "priority_only":
        serve = int(_num(scenario.get("priority_terminals")))
    else:
        serve = int(_num(scenario.get("terminals")))
    uav_count = int(_num(scenario.get("uav_count")))
    uses_uav = bool(plan.get("uses_uav_relay", True)) and uav_count > 0
    mission = int(_num(scenario.get("mission_duration_min")))
    adapted = dict(plan)
    adapted.update({
        "coverage": coverage,
        "serve_terminal_count": serve,
        "mbps_per_terminal": _num(scenario.get("demand_mbps_per_terminal")),
        "uses_uav_relay": uses_uav,
        "uav_used": min(int(_num(plan.get("uav_used"), 1 if uses_uav else 0)), uav_count) if uses_uav else 0,
        "uav_continuous_min": mission if uses_uav else 0,
    })
    if uses_uav and adapted["uav_used"] < 1:
        adapted["uav_used"] = 1
    return adapted


def apply_confirmed_patch(plan: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    revised = dict(plan)
    for key, value in (patch or {}).items():
        if key in _PATCH_KEYS:
            revised[key] = value
    revised["source"] = "confirmed_rule_revision"
    revised["source_note"] = "用户确认的规则修订。资源上限仍来自场景参数，检查结果由程序重算。"
    return revised


def check_plan(scenario: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    param_errors = validate_scenario(scenario)
    demand = _num(plan.get("serve_terminal_count")) * _num(plan.get("mbps_per_terminal"))
    available = available_backhaul_mbps(scenario)
    capacity_ok = demand <= available + 1e-9
    capacity_detail = (
        f"业务总需求 {demand:g} Mbps，可用回传容量 {available:g} Mbps"
        + ("。" if capacity_ok else "，需求超过容量上限。")
    )

    uses_uav = bool(plan.get("uses_uav_relay"))
    required_min = int(_num(plan.get("uav_continuous_min"))) if uses_uav else 0
    available_min = int(_num(scenario.get("uav_count"))) * int(_num(scenario.get("uav_endurance_min")))
    if not uses_uav:
        endurance_ok = True
        endurance_detail = "方案未使用无人机中继，不检查续航。"
    else:
        endurance_ok = available_min + 1e-9 >= required_min and int(_num(scenario.get("uav_count"))) >= 1
        endurance_detail = (
            f"无人机需连续保障 {required_min} 分钟，现有 {int(_num(scenario.get('uav_count')))} 架"
            f"合计续航 {available_min} 分钟"
            + ("。" if endurance_ok else "，没有额外接替资源，续航不足。")
        )

    uav_used = int(_num(plan.get("uav_used")))
    uav_count = int(_num(scenario.get("uav_count")))
    devices_ok = uav_used <= uav_count and uav_used >= 0
    if uses_uav and uav_count < 1:
        devices_ok = False
    devices_detail = (
        f"方案使用无人机 {uav_used} 架，可用 {uav_count} 架。"
        if devices_ok
        else f"方案使用无人机 {uav_used} 架，超过可用数量 {uav_count} 架。"
    )

    items = [
        {
            "id": "params",
            "title": "场景参数完整性",
            "passed": not param_errors,
            "detail": "场景参数完整且有效。" if not param_errors else "；".join(param_errors),
        },
        {
            "id": "capacity",
            "title": "回传容量",
            "passed": capacity_ok and not param_errors,
            "detail": capacity_detail,
            "demand_mbps": demand,
            "available_mbps": available,
        },
        {
            "id": "endurance",
            "title": "无人机续航",
            "passed": endurance_ok and not param_errors,
            "detail": endurance_detail,
            "required_min": required_min,
            "available_min": available_min,
        },
        {
            "id": "devices",
            "title": "设备数量",
            "passed": devices_ok and not param_errors,
            "detail": devices_detail,
            "uav_used": uav_used,
            "uav_available": uav_count,
        },
    ]
    # 参数无效时，容量和续航数字仍展示，但不算通过，避免残缺输入被当成可部署方案。
    failed_ids = [item["id"] for item in items if not item["passed"]]
    return {
        "engine": ENGINE_ID,
        "items": items,
        "failed_ids": failed_ids,
        "all_passed": not failed_ids,
        "demand_mbps": demand,
        "backhaul_mbps": available,
        "disclaimer": DISCLAIMER,
        "not_verified": ["无线覆盖", "真实吞吐量", "端到端时延", "部署安全"],
    }


def suggest_revisions(
    scenario: Dict[str, Any],
    plan: Dict[str, Any],
    check: Dict[str, Any],
) -> List[Dict[str, Any]]:
    failed = set(check.get("failed_ids") or [])
    suggestions: List[Dict[str, Any]] = []
    backhaul = available_backhaul_mbps(scenario)
    rate = _num(scenario.get("demand_mbps_per_terminal"))
    priority_count = int(_num(scenario.get("priority_terminals")))
    priority_demand = priority_count * rate

    if "capacity" in failed and plan.get("coverage") != "priority_only":
        if priority_demand <= backhaul + 1e-9 and priority_count >= 1:
            suggestions.append({
                "id": "prioritize_rescue_terminals",
                "applicable": True,
                "requires_user_confirmation": True,
                "changes_service_requirement": True,
                "invents_resources": False,
                "title": "改为优先保障救援终端",
                "detail": (
                    f"同时服务终端从 {int(_num(plan.get('serve_terminal_count')))} 调整为"
                    f"救援优先终端 {priority_count}，单终端速率仍为 {rate:g} Mbps。"
                    "其余终端不在本方案中同时保障。确认后才会生成新版本并重新检查。"
                ),
                "patch": {
                    "coverage": "priority_only",
                    "serve_terminal_count": priority_count,
                    "mbps_per_terminal": rate,
                    "service_requirement_changed": True,
                    "change_note": "用户确认后，仅同时保障救援优先终端，不降低单终端速率，不增加回传或无人机。",
                },
            })
        else:
            suggestions.append({
                "id": "capacity_unsatisfiable_without_user_resource_change",
                "applicable": False,
                "requires_user_confirmation": False,
                "changes_service_requirement": False,
                "invents_resources": False,
                "title": "容量冲突无法自动消除",
                "detail": (
                    "即使只保障优先终端，需求仍超过回传容量。"
                    "程序不会自动增加容量或降低单终端速率。请在场景参数中修改后再检查。"
                ),
            })

    if "endurance" in failed:
        suggestions.append({
            "id": "endurance_requires_user_resource_change",
            "applicable": False,
            "requires_user_confirmation": False,
            "changes_service_requirement": False,
            "invents_resources": False,
            "title": "续航冲突需要用户调整资源或任务时长",
            "detail": (
                f"任务需要无人机连续保障 {int(_num(plan.get('uav_continuous_min')))} 分钟，"
                f"现有 {int(_num(scenario.get('uav_count')))} 架合计续航 "
                f"{int(_num(scenario.get('uav_count'))) * int(_num(scenario.get('uav_endurance_min')))} 分钟。"
                "程序不会自动增加无人机、延长续航或缩短任务。"
            ),
        })
    return suggestions


def overall_status(
    previous: Optional[Dict[str, Any]],
    current: Dict[str, Any],
) -> Tuple[str, str]:
    if current.get("all_passed"):
        return (
            "pass",
            "资源约束预检已通过。这不代表无线覆盖、吞吐量、端到端时延或部署安全已经验证。",
        )
    prev_failed = set((previous or {}).get("failed_ids") or [])
    curr_failed = set(current.get("failed_ids") or [])
    fixed = prev_failed - curr_failed
    if fixed and curr_failed:
        return "partial", PARTIAL_SUMMARY
    details = [
        item["detail"]
        for item in current.get("items") or []
        if item.get("id") in curr_failed
    ]
    return "fail", "；".join(details) if details else "资源约束预检未通过。"


def scenario_snapshot(scenario: Dict[str, Any]) -> Dict[str, Any]:
    snap = copy.deepcopy(scenario)
    snap["parameter_origin"] = snap.get("parameter_origin") or "simulated_user_input"
    return snap
