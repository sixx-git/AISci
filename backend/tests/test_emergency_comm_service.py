"""6G 预检写入项目版本，并由大家长记录协调动作。"""
from datetime import datetime

from app.core.project_modes import is_emergency_6g_mode, normalize_project_mode
from app.models.project import Project, ProjectStatus
from app.services.emergency_comm.service import EmergencyCommService


def test_mode_stays_emergency_6g():
    assert normalize_project_mode("emergency_6g") == "emergency_6g"
    assert is_emergency_6g_mode("emergency_6g") is True
    assert normalize_project_mode("bogus") == "general"


def test_confirm_keeps_versions_and_partial_status(db_session):
    project = Project(
        name="近海岛屿应急通信",
        project_mode="emergency_6g",
        status=ProjectStatus.DRAFT,
        config={},
        created_at=datetime.now(),
    )
    db_session.add(project)
    db_session.commit()

    svc = EmergencyCommService(db_session)
    first = svc.ensure(project.id)
    assert first["versions"][0]["status"] == "fail"
    assert first["versions"][0]["coordinator"]["agent"] == "CoordinatorAgent"
    assert first["integration"]["literature_facts"] == "not_used"
    assert first["integration"]["qwen_revision"] == "not_enabled"

    second = svc.confirm(project.id, "prioritize_rescue_terminals")
    assert len(second["versions"]) == 2
    latest = second["versions"][-1]
    assert latest["status"] == "partial"
    assert latest["summary"] == "部分问题已解决、整体方案仍不满足条件"
    assert latest["comparison"]["demand_mbps"] == {"before": 30, "after": 10}
    assert "capacity" in latest["comparison"]["newly_passed"]
    assert "endurance" in latest["comparison"]["still_failing"]
    assert latest["coordinator"]["suggestion"] == "await_user_parameter_change"

    db_session.refresh(project)
    stored = (project.config or {})["emergency_comm"]["versions"]
    assert len(stored) == 2
