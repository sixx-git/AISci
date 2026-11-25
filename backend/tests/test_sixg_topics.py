"""6G 专题、自定义解析和预检记录。"""
from datetime import datetime

from app.models.project import Project, ProjectStatus
from app.services.emergency_comm.service import EmergencyCommError, EmergencyCommService
from app.services.sixg.parse import normalize_custom_parse
from app.services.sixg.profile import apply_sixg_profile
from app.services.sixg.records import render_sixg_appendix, save_precheck_report
from app.services.sixg.topics import get_topic


def test_predefined_topics_do_not_invent_checks():
    emergency = get_topic("emergency_comm")
    edge = get_topic("edge_computing")
    isac = get_topic("isac")
    assert emergency["tool"] == "emergency_constraints"
    assert emergency["verification_status"] == "deterministic"
    assert edge["tool"] is None
    assert edge["verification_status"] == "待专业验证"
    assert isac["verification_status"] == "待专业验证"
    assert "仿真" in isac["verification_note"] or "仿真" in isac["constraints"]


def test_llm_numbers_are_not_measurements():
    parsed = normalize_custom_parse(
        "研究通感一体化的波形折中",
        {
            "domain": "通感一体化",
            "parameters": [{"name": "带宽", "value": "100", "unit": "MHz"}],
            "applicable_tools": ["fake_simulator", "literature_pipeline"],
        },
    )
    item = parsed["parameters"][0]
    assert item["origin"] == "llm_inferred"
    assert item["is_measured"] is False
    assert item["confirmed"] is False
    assert "fake_simulator" not in parsed["applicable_tools"]
    assert parsed["verification_status"] == "待专业验证"


def test_user_written_number_still_needs_confirmation():
    parsed = normalize_custom_parse(
        "终端带宽 100 MHz",
        {"parameters": [{"name": "带宽", "value": "100", "unit": "MHz"}]},
    )
    item = parsed["parameters"][0]
    assert item["origin"] == "user_supplied"
    assert item["is_measured"] is False
    assert item["confirmed"] is False


def test_edge_topic_does_not_open_emergency_checker(db_session):
    project = Project(
        name="算网协同",
        project_mode="emergency_6g",
        status=ProjectStatus.DRAFT,
        research_question="",
        config={},
        created_at=datetime.now(),
    )
    db_session.add(project)
    db_session.commit()
    apply_sixg_profile(project, topic_id="edge_computing", execution_mode="full")
    db_session.add(project)
    db_session.commit()
    assert project.research_domain.startswith("6G")
    assert "边缘智能" in project.research_question
    assert (project.config or {}).get("emergency_comm") is None
    try:
        EmergencyCommService(db_session).ensure(project.id)
        raised = False
    except EmergencyCommError:
        raised = True
    assert raised is True


def test_emergency_record_enters_report(db_session):
    project = Project(
        name="应急通信",
        project_mode="emergency_6g",
        status=ProjectStatus.DRAFT,
        config={},
        created_at=datetime.now(),
    )
    db_session.add(project)
    db_session.commit()
    apply_sixg_profile(project, topic_id="emergency_comm", execution_mode="quick")
    db_session.add(project)
    db_session.commit()
    EmergencyCommService(db_session).ensure(project.id)
    db_session.refresh(project)
    appendix = render_sixg_appendix(project)
    assert "30" in appendix
    assert "20" in appendix
    assert "大家长只记录" in appendix
    report = save_precheck_report(db_session, project)
    assert report.model_used == "deterministic_rules_v1"
    assert report.extra_metadata["llm_simulation"] is False
    assert "30" in report.results
