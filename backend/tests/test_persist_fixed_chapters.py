"""
测试 _persist_fixed_chapters_to_db 和 _save_hints_to_advice_table

测试方法通过直接操作数据库记录来验证持久化逻辑的正确性，
使用 SQLite 内存数据库，不依赖外部服务。
"""
import uuid
from unittest.mock import patch
import pytest
from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.core import Base
from app.models.pipeline import PipelineRun, PipelineStageExecution, PipelineStage, PipelineStatus
from app.models.project import Report, Project, ProjectStatus
from app.models.coordinator import CoordinatorAdvice
from app.services.pipeline_service import PipelineService


@pytest.fixture(scope="session")
def db_engine():
    """使用文件数据库确保跨会话可见"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_sessionmaker(db_engine):
    return sessionmaker(bind=db_engine)


@pytest.fixture(scope="function")
def db_session(test_sessionmaker):
    session = test_sessionmaker()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def mock_session_local(test_sessionmaker, monkeypatch):
    """将 app.core.database.SessionLocal 替换为测试 sessionmaker"""
    import app.core.database
    monkeypatch.setattr(app.core.database, "SessionLocal", test_sessionmaker)


@pytest.fixture
def test_project(db_session):
    project = Project(
        name="Test Project",
        description="test",
        research_question="test question",
        status=ProjectStatus.DRAFT,
        created_at=datetime.now(),
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_pipeline_run(db_session, test_project):
    run = PipelineRun(
        project_id=test_project.id,
        run_id=str(uuid.uuid4()),
        research_question="test",
        status=PipelineStatus.COMPLETED,
        output_data={
            "report_generation": {
                "chapters": {
                    "results": "原始结果章节内容",
                    "methods": "原始方法章节内容",
                }
            }
        },
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


@pytest.fixture
def test_report(db_session, test_project):
    report = Report(
        project_id=test_project.id,
        title="Test Report",
        paper_title="Test Paper",
        paper_abstract="Test Abstract",
        problem_statement="原始问题陈述",
        rationale="原始原理依据",
        technical_details="原始技术细节",
        datasets="原始数据集说明",
        source="原始源数据说明",
        target="原始目标说明",
        methods="原始方法章节内容",
        experiments="原始实验设计",
        results="原始结果章节内容",
        references="原始参考文献",
        markdown_content="原始完整内容",
        status="draft",
        created_at=datetime.now(),
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


@pytest.fixture
def test_stage_execution(db_session, test_pipeline_run):
    exec_record = PipelineStageExecution(
        pipeline_run_id=test_pipeline_run.id,
        stage=PipelineStage.REPORT_GENERATION,
        stage_order=1,
        status=PipelineStatus.COMPLETED,
        output_data={
            "chapters": {
                "results": "原始结果章节内容",
                "methods": "原始方法章节内容",
            }
        },
        created_at=datetime.now(),
    )
    db_session.add(exec_record)
    db_session.commit()
    db_session.refresh(exec_record)
    return exec_record


class TestPersistFixedChaptersToDb:
    """测试 _persist_fixed_chapters_to_db 方法"""

    def test_updates_all_three_models(
        self, db_session, test_project, test_pipeline_run, test_report, test_stage_execution, mock_session_local
    ):
        """验证修复内容同时写入 PipelineStageExecution、PipelineRun 和 Report"""
        svc = PipelineService(db_session)
        fixed_chapters = {
            "results": "修复后的结果内容",
        }

        svc._persist_fixed_chapters_to_db(test_pipeline_run.run_id, fixed_chapters)

        # 验证 PipelineStageExecution 已更新
        db_session.refresh(test_stage_execution)
        assert test_stage_execution.output_data["chapters"]["results"] == "修复后的结果内容"
        assert test_stage_execution.output_data["chapters"]["methods"] == "原始方法章节内容"  # 未修改的保留

        # 验证 PipelineRun 已更新
        db_session.refresh(test_pipeline_run)
        assert test_pipeline_run.output_data["report_generation"]["chapters"]["results"] == "修复后的结果内容"
        assert test_pipeline_run.output_data["report_generation"]["chapters"]["methods"] == "原始方法章节内容"

        # 验证 Report 模型已更新
        db_session.refresh(test_report)
        assert test_report.results == "修复后的结果内容"
        assert test_report.methods == "原始方法章节内容"  # 未修改的保留

    def test_updates_multiple_chapters(
        self, db_session, test_project, test_pipeline_run, test_report, test_stage_execution, mock_session_local
    ):
        """验证同时修复多个章节"""
        svc = PipelineService(db_session)
        fixed_chapters = {
            "results": "修复后结果",
            "methods": "修复后方法",
        }

        svc._persist_fixed_chapters_to_db(test_pipeline_run.run_id, fixed_chapters)

        db_session.refresh(test_report)
        assert test_report.results == "修复后结果"
        assert test_report.methods == "修复后方法"

    def test_skips_unknown_run_id(self, db_session, test_project, test_report, test_stage_execution, mock_session_local):
        """验证不存在的 run_id 不会报错"""
        svc = PipelineService(db_session)
        svc._persist_fixed_chapters_to_db("nonexistent-run-id", {"results": "xxx"})
        # 不应抛出异常，Report 内容不变
        db_session.refresh(test_report)
        assert test_report.results == "原始结果章节内容"


class TestSaveHintsToAdviceTable:
    """测试 _save_hints_to_advice_table 方法"""

    def _make_hint(self, hint_id, stage="report_generation", severity="high",
                   message="test", remediation="auto_skip", action=None,
                   fix_status=None, fix_detail=None, source="predefined"):
        return {
            "id": hint_id,
            "stage": stage,
            "severity": severity,
            "message": message,
            "remediation": remediation,
            "action": action or {"type": "auto", "suggestion": "continue", "description": ""},
            "source": source,
            "fix_status": fix_status,
            "fix_detail": fix_detail,
        }

    def test_inserts_new_hints(self, db_session, test_project, mock_session_local):
        """验证新 hints 正确插入"""
        svc = PipelineService(db_session)
        hints = [self._make_hint("hint_1", message="报告内容质量问题", remediation="auto_fix_report")]

        svc._save_hints_to_advice_table(hints, test_project.id)

        records = db_session.query(CoordinatorAdvice).filter(
            CoordinatorAdvice.project_id == test_project.id,
        ).all()
        assert len(records) == 1
        assert records[0].title == "报告内容质量问题"
        assert records[0].extra_data["hint_id"] == "hint_1"

    def test_updates_existing_hint_by_hint_id(self, db_session, test_project, mock_session_local):
        """验证通过 hint_id 更新已有记录（保留 fix_status）"""
        svc = PipelineService(db_session)
        hints_v1 = [self._make_hint("hint_1", message="报告内容质量问题", remediation="auto_fix_report")]
        svc._save_hints_to_advice_table(hints_v1, test_project.id)

        # 模拟后台线程更新 fix_status
        hints_v2 = [self._make_hint("hint_1", message="报告内容质量问题", remediation="auto_fix_report",
                                    fix_status="completed", fix_detail="已修复 1 个章节: results")]
        svc._save_hints_to_advice_table(hints_v2, test_project.id)

        # 验证 fix_status 已更新
        records = db_session.query(CoordinatorAdvice).filter(
            CoordinatorAdvice.project_id == test_project.id,
        ).all()
        assert len(records) == 1  # 没有重复插入
        assert records[0].extra_data["fix_status"] == "completed"
        assert records[0].extra_data["fix_detail"] == "已修复 1 个章节: results"

    def test_preserves_fix_status_when_new_data_has_none(self, db_session, test_project, mock_session_local):
        """验证更新时如果新数据没有 fix_status，保留旧数据"""
        svc = PipelineService(db_session)
        hints_v1 = [self._make_hint("hint_1", message="报告内容质量问题", remediation="auto_fix_report",
                                    fix_status="completed", fix_detail="已修复")]
        svc._save_hints_to_advice_table(hints_v1, test_project.id)

        # 再次保存（新数据没有 fix_status，模拟主线程的后续阶段检查）
        hints_v2 = [self._make_hint("hint_1", message="报告内容质量问题", remediation="auto_fix_report")]
        svc._save_hints_to_advice_table(hints_v2, test_project.id)

        # 验证 fix_status 被保留（因为新数据是 None）
        records = db_session.query(CoordinatorAdvice).filter(
            CoordinatorAdvice.project_id == test_project.id,
        ).all()
        assert len(records) == 1
        assert records[0].extra_data["fix_status"] == "completed"  # 保留旧值

    def test_removes_stale_hints(self, db_session, test_project, mock_session_local):
        """验证旧阶段检查结果被清理"""
        svc = PipelineService(db_session)
        hints_v1 = [
            self._make_hint("hint_old", stage="literature_mining", severity="low", message="旧提示"),
            self._make_hint("hint_new", message="新提示"),
        ]
        svc._save_hints_to_advice_table(hints_v1, test_project.id)

        # 只保存新 hint（旧 hint 应被删除）
        hints_v2 = [self._make_hint("hint_new", message="新提示")]
        svc._save_hints_to_advice_table(hints_v2, test_project.id)

        records = db_session.query(CoordinatorAdvice).filter(
            CoordinatorAdvice.project_id == test_project.id,
        ).all()
        assert len(records) == 1
        assert records[0].extra_data["hint_id"] == "hint_new"