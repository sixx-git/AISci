"""把应急通信预检结果写入项目 config，并由大家长记录修订协调。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.coordinator_agent import CoordinatorAgent
from app.core.project_modes import is_emergency_6g_mode
from app.models.project import Project
from app.services.sixg.topics import EMERGENCY_TOPIC, topic_id_from_config
from app.services.emergency_comm.constraints import (
    DISCLAIMER,
    adapt_plan_to_scenario,
    apply_confirmed_patch,
    build_initial_plan,
    check_plan,
    demo_scenario,
    overall_status,
    scenario_snapshot,
    suggest_revisions,
)

APP_NAME = "溯源智研·6G应急通信方案智能评审"
DEFAULT_QUESTION = (
    "在空天地融合应急通信场景下，如何让 AI 生成的候选通信保障方案"
    "满足基本资源约束，并能够根据检查结果持续修订？"
)

_SCENARIO_INTS = (
    "terminals",
    "priority_terminals",
    "uav_count",
    "uav_endurance_min",
    "mission_duration_min",
)
_SCENARIO_FLOATS = (
    "demand_mbps_per_terminal",
    "satellite_backhaul_mbps",
    "ground_backhaul_mbps",
)
_SCENARIO_TEXT = ("location", "disaster")


class EmergencyCommError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class EmergencyCommService:
    def __init__(self, db: Session):
        self.db = db

    def ensure(self, project_id: str) -> Dict[str, Any]:
        project = self._require_emergency_topic(project_id)
        state = self._load(project)
        if not state:
            state = self._fresh_state()
            self._save(project, state)
        return self._public(state)

    def update_scenario(self, project_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        project = self._require_emergency_topic(project_id)
        state = self._load(project) or self._fresh_state()
        scenario = dict(state["scenario"])
        self._apply_scenario_patch(scenario, patch)
        active = state["versions"][-1]
        plan = adapt_plan_to_scenario(active["plan"], scenario)
        state["scenario"] = scenario_snapshot(scenario)
        self._append_version(
            state,
            plan=plan,
            origin="user_scenario_edit",
            previous=active["check"],
        )
        self._save(project, state)
        return self._public(state)

    def confirm(self, project_id: str, suggestion_id: str) -> Dict[str, Any]:
        project = self._require_emergency_topic(project_id)
        state = self._load(project) or self._fresh_state()
        active = state["versions"][-1]
        suggestions = suggest_revisions(state["scenario"], active["plan"], active["check"])
        match = next((item for item in suggestions if item["id"] == suggestion_id), None)
        if not match or not match.get("applicable") or not match.get("patch"):
            raise EmergencyCommError("该修订不能直接应用。请调整场景参数，或确认另一条可执行建议。")
        plan = apply_confirmed_patch(active["plan"], match["patch"])
        self._append_version(
            state,
            plan=plan,
            origin="confirmed_revision",
            previous=active["check"],
            suggestion_id=suggestion_id,
        )
        self._save(project, state)
        return self._public(state)

    def _require_emergency_topic(self, project_id: str) -> Project:
        project = self._require_project(project_id)
        if topic_id_from_config(project.config) != EMERGENCY_TOPIC:
            raise EmergencyCommError("当前 6G 专题没有确定性预检工具，专业指标保持待专业验证")
        return project

    def _require_project(self, project_id: str) -> Project:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise EmergencyCommError("项目不存在", 404)
        if not is_emergency_6g_mode(getattr(project, "project_mode", None)):
            raise EmergencyCommError("当前项目不是 6G 应急通信应用")
        return project

    def _load(self, project: Project) -> Optional[Dict[str, Any]]:
        cfg = project.config or {}
        state = cfg.get("emergency_comm")
        return dict(state) if isinstance(state, dict) and state.get("versions") else None

    def _save(self, project: Project, state: Dict[str, Any]) -> None:
        cfg = dict(project.config or {})
        cfg["emergency_comm"] = state
        project.config = cfg
        flag_modified(project, "config")
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

    def _fresh_state(self) -> Dict[str, Any]:
        scenario = demo_scenario()
        plan = build_initial_plan(scenario)
        state: Dict[str, Any] = {
            "app": APP_NAME,
            "disclaimer": DISCLAIMER,
            "integration": {
                "constraint_engine": "deterministic_rules_v1",
                "coordinator": "CoordinatorAgent.coordinate_emergency_precheck",
                "persistence": "project.config.emergency_comm",
                "qwen_revision": "not_enabled",
                "literature_facts": "not_used",
                "iterative_experiment": "not_used",
                "pipeline_stages": "unchanged",
            },
            "scenario": scenario_snapshot(scenario),
            "versions": [],
        }
        self._append_version(state, plan=plan, origin="initial_template", previous=None)
        return state

    def _append_version(
        self,
        state: Dict[str, Any],
        *,
        plan: Dict[str, Any],
        origin: str,
        previous: Optional[Dict[str, Any]],
        suggestion_id: Optional[str] = None,
    ) -> None:
        scenario = state["scenario"]
        check = check_plan(scenario, plan)
        suggestions = suggest_revisions(scenario, plan, check)
        status, summary = overall_status(previous, check)
        coordinator = CoordinatorAgent().coordinate_emergency_precheck(
            check, suggestions, status, summary
        )
        version_no = len(state["versions"]) + 1
        record: Dict[str, Any] = {
            "version": version_no,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "origin": origin,
            "suggestion_id": suggestion_id,
            "plan": plan,
            "check": check,
            "status": status,
            "summary": summary,
            "coordinator": coordinator,
        }
        if state["versions"]:
            prev = state["versions"][-1]
            prev_failed = set(prev["check"].get("failed_ids") or [])
            curr_failed = set(check.get("failed_ids") or [])
            record["comparison"] = {
                "from_version": prev["version"],
                "to_version": version_no,
                "demand_mbps": {
                    "before": prev["check"].get("demand_mbps"),
                    "after": check.get("demand_mbps"),
                },
                "serve_terminal_count": {
                    "before": prev["plan"].get("serve_terminal_count"),
                    "after": plan.get("serve_terminal_count"),
                },
                "uav_continuous_min": {
                    "before": prev["plan"].get("uav_continuous_min"),
                    "after": plan.get("uav_continuous_min"),
                },
                "newly_passed": sorted(prev_failed - curr_failed),
                "still_failing": sorted(curr_failed),
            }
        state["versions"].append(record)

    def _public(self, state: Dict[str, Any]) -> Dict[str, Any]:
        active = state["versions"][-1]
        public = dict(state)
        public["active_version"] = active["version"]
        public["pending_suggestions"] = suggest_revisions(
            state["scenario"], active["plan"], active["check"]
        )
        return public

    @staticmethod
    def _apply_scenario_patch(scenario: Dict[str, Any], patch: Dict[str, Any]) -> None:
        for key in _SCENARIO_TEXT:
            if patch.get(key) is not None:
                scenario[key] = str(patch[key]).strip()
        for key in _SCENARIO_INTS:
            if patch.get(key) is not None:
                scenario[key] = int(patch[key])
        for key in _SCENARIO_FLOATS:
            if patch.get(key) is not None:
                scenario[key] = float(patch[key])
        scenario["parameter_origin"] = "simulated_user_input"
