"""报告中心浏览 API 测试。"""
from datetime import datetime, timedelta

import pytest

from app.models import Project, ProjectStatus
from app.models.project import Report
from app.services.report_service import ReportService


def _make_report(db, project, *, title: str, created_at: datetime):
    report = Report(
        project_id=project.id,
        title=title,
        paper_title=title,
        paper_abstract="abstract",
        problem_statement="p",
        rationale="r",
        technical_details="t",
        datasets="d",
        source="s",
        target="t",
        methods="m",
        experiments="e",
        results="r",
        references="[]",
        markdown_content="# test",
        status="generated",
        version=1,
        created_at=created_at,
    )
    db.add(report)
    db.commit()
    return report


@pytest.fixture
def report_fixtures(db_session):
    general = Project(
        name="通用项目",
        project_mode="general",
        research_question="城市热岛效应研究",
        status=ProjectStatus.COMPLETED,
        created_at=datetime.now(),
    )
    fl = Project(
        name="联邦项目",
        project_mode="federated_learning",
        research_question="联邦学习 Non-IID 优化",
        status=ProjectStatus.COMPLETED,
        created_at=datetime.now(),
    )
    db_session.add_all([general, fl])
    db_session.commit()
    db_session.refresh(general)
    db_session.refresh(fl)

    now = datetime.now()
    prefix = f"browse-{datetime.now().timestamp()}"
    _make_report(db_session, general, title=f"{prefix}-通用报告-新", created_at=now)
    _make_report(
        db_session,
        fl,
        title=f"{prefix}-联邦报告-旧",
        created_at=now - timedelta(days=40),
    )
    return general, fl, prefix


def test_browse_reports_filter_by_mode(db_session, report_fixtures):
    _, _, prefix = report_fixtures
    svc = ReportService(db_session)
    items, total = svc.browse_reports(project_mode="federated_learning", keyword=prefix)
    assert total == 1
    assert items[0].project_mode == "federated_learning"


def test_browse_reports_filter_by_date(db_session, report_fixtures):
    _, _, prefix = report_fixtures
    svc = ReportService(db_session)
    date_from = datetime.now() - timedelta(days=7)
    items, total = svc.browse_reports(date_from=date_from, keyword=prefix)
    assert total == 1
    assert "通用" in items[0].title


def test_browse_reports_pagination(db_session, report_fixtures):
    _, _, prefix = report_fixtures
    svc = ReportService(db_session)
    items, total = svc.browse_reports(page=1, page_size=1, keyword=prefix)
    assert total == 2
    assert len(items) == 1
