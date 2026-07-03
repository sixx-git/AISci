"""项目删除级联测试。"""
import pytest
from datetime import datetime

from app.models import Project, ProjectStatus
from app.models.pipeline import PipelineRun, PipelineStageExecution, PipelineStatus, PipelineStage
from app.models.research import Hypothesis, Evidence, SmallValidation, ExperimentDesign
from app.services.project_service import ProjectService


@pytest.fixture
def project_with_relations(db_session):
    project = Project(
        name="Delete Me",
        status=ProjectStatus.DRAFT,
        created_at=datetime.now(),
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    hyp = Hypothesis(
        project_id=project.id,
        research_question="q",
        hypothesis="h",
        rationale="r",
        novelty="n",
        testability="t",
        required_data="d",
        possible_method="m",
        risk="k",
    )
    db_session.add(hyp)
    db_session.commit()
    db_session.refresh(hyp)

    db_session.add(Evidence(
        project_id=project.id,
        hypothesis_id=hyp.id,
        fact_text="fact",
    ))

    db_session.add(ExperimentDesign(
        project_id=project.id,
        hypothesis_id=hyp.id,
        hypothesis="h",
        methods="m",
        datasets="d",
        source_data="s",
        target_data="t",
        baselines="b",
        metrics="x",
        experimental_steps="e",
        expected_results="er",
        limitations="l",
    ))
    db_session.commit()

    design = db_session.query(ExperimentDesign).filter_by(project_id=project.id).first()
    db_session.add(SmallValidation(
        project_id=project.id,
        experiment_design_id=design.id,
        hypothesis="h",
        analysis_script="print(1)",
    ))

    run = PipelineRun(
        project_id=project.id,
        run_id="run-test-001",
        research_question="q",
        status=PipelineStatus.COMPLETED,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    db_session.add(PipelineStageExecution(
        pipeline_run_id=run.id,
        stage=PipelineStage.LITERATURE_MINING,
        status="completed",
        stage_order=1,
    ))
    db_session.commit()
    return project


def test_delete_project_with_relations(db_session, project_with_relations):
    svc = ProjectService(db_session)
    pid = str(project_with_relations.id)
    assert svc.delete_project(pid) is True
    assert svc.get_project(pid) is None
