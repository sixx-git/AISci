"""6G 应急通信资源约束预检：确定性规则，不调用大模型。"""
from app.services.emergency_comm.constraints import (
    apply_confirmed_patch,
    build_initial_plan,
    check_plan,
    demo_scenario,
    overall_status,
    suggest_revisions,
)


def test_demo_case_flags_capacity_and_endurance_conflicts():
    scenario = demo_scenario()
    plan = build_initial_plan(scenario)
    result = check_plan(scenario, plan)

    by_id = {item["id"]: item for item in result["items"]}
    assert by_id["capacity"]["passed"] is False
    assert by_id["capacity"]["demand_mbps"] == 30
    assert by_id["capacity"]["available_mbps"] == 20
    assert "30" in by_id["capacity"]["detail"]
    assert "20" in by_id["capacity"]["detail"]

    assert by_id["endurance"]["passed"] is False
    assert by_id["endurance"]["required_min"] == 90
    assert by_id["endurance"]["available_min"] == 60
    assert by_id["devices"]["passed"] is True
    assert by_id["params"]["passed"] is True
    assert result["all_passed"] is False
    assert result["engine"] == "deterministic_rules_v1"


def test_priority_revision_clears_capacity_but_not_endurance():
    scenario = demo_scenario()
    plan = build_initial_plan(scenario)
    first = check_plan(scenario, plan)
    suggestions = suggest_revisions(scenario, plan, first)
    priority = next(item for item in suggestions if item["id"] == "prioritize_rescue_terminals")

    assert priority["requires_user_confirmation"] is True
    assert priority["changes_service_requirement"] is True
    assert priority["invents_resources"] is False
    assert priority["patch"]["serve_terminal_count"] == 10
    assert priority["patch"]["mbps_per_terminal"] == 1.0
    assert "uav_count" not in priority["patch"]
    assert "satellite_backhaul_mbps" not in priority["patch"]

    revised = apply_confirmed_patch(plan, priority["patch"])
    second = check_plan(scenario, revised)
    status, summary = overall_status(first, second)

    by_id = {item["id"]: item for item in second["items"]}
    assert by_id["capacity"]["passed"] is True
    assert by_id["capacity"]["demand_mbps"] == 10
    assert by_id["endurance"]["passed"] is False
    assert status == "partial"
    assert summary == "部分问题已解决、整体方案仍不满足条件"


def test_revision_does_not_invent_a_passing_endurance_plan():
    scenario = demo_scenario()
    plan = build_initial_plan(scenario)
    result = check_plan(scenario, plan)
    suggestions = suggest_revisions(scenario, plan, result)
    endurance = next(item for item in suggestions if item["id"] == "endurance_requires_user_resource_change")

    assert endurance["applicable"] is False
    assert endurance.get("patch") in (None, {})


def test_user_can_shorten_mission_and_pass_endurance_after_priority():
    scenario = demo_scenario()
    plan = build_initial_plan(scenario)
    first = check_plan(scenario, plan)
    patch = next(
        item["patch"]
        for item in suggest_revisions(scenario, plan, first)
        if item["id"] == "prioritize_rescue_terminals"
    )
    revised = apply_confirmed_patch(plan, patch)
    shortened = {**scenario, "mission_duration_min": 60}
    adapted = build_initial_plan(shortened)
    adapted["coverage"] = "priority_only"
    adapted["serve_terminal_count"] = shortened["priority_terminals"]
    adapted["service_requirement_changed"] = True
    # 续航按新任务时长重算，容量策略保持用户已确认的优先保障
    adapted["uav_continuous_min"] = shortened["mission_duration_min"]
    checked = check_plan(shortened, adapted)
    assert checked["all_passed"] is True


def test_incomplete_scenario_fails_param_check():
    scenario = demo_scenario()
    scenario["priority_terminals"] = 40
    plan = build_initial_plan(scenario)
    result = check_plan(scenario, plan)
    params = next(item for item in result["items"] if item["id"] == "params")
    assert params["passed"] is False
    assert result["all_passed"] is False
