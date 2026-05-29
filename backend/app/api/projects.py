"""
项目 API 路由
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.schemas.common import (
    ResponseModel,
    PaginatedResponse,
    PageInfo,
    success_response
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectQuery,
    ProjectDetail,
    ProjectList,
    UploadResponse,
    DocumentInfo
)
from app.schemas.research import HypothesisResponse, ExperimentDesignDBResponse
from app.services.project_service import ProjectService, DocumentService
from app.services.hypothesis_service import HypothesisService
from app.services.experiment_service import ExperimentDesignService
from app.models.pipeline import PipelineRun, PipelineStageExecution, PipelineStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


# ============= 项目管理 API =============

@router.post("", response_model=ResponseModel[ProjectDetail])
def create_project(
    data: ProjectCreate,
    service: ProjectService = Depends(get_project_service)
):
    """创建项目"""
    project = service.create_project(data)
    return success_response(
        data=ProjectDetail.model_validate(project),
        message="项目创建成功"
    )


@router.get("", response_model=ResponseModel[PaginatedResponse[ProjectList]])
def list_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="项目状态"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    service: ProjectService = Depends(get_project_service)
):
    """项目列表"""
    query = ProjectQuery(
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword
    )
    
    projects, total = service.list_projects(query)
    total_pages = (total + page_size - 1) // page_size
    
    # 转换为响应格式
    project_list = []
    for project in projects:
        p = ProjectList.model_validate(project)
        p.document_count = 0  # 暂时设为0
        project_list.append(p)
    
    return success_response(
        data=PaginatedResponse(
            list=project_list,
            pagination=PageInfo(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages
            )
        ),
        message="获取项目列表成功"
    )


@router.get("/{project_id}", response_model=ResponseModel[ProjectDetail])
def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service)
):
    """获取项目详情"""
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return success_response(
        data=ProjectDetail.model_validate(project),
        message="获取项目详情成功"
    )


@router.put("/{project_id}", response_model=ResponseModel[ProjectDetail])
def update_project(
    project_id: str,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_project_service)
):
    """全量更新项目"""
    project = service.update_project(project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return success_response(
        data=ProjectDetail.model_validate(project),
        message="项目更新成功"
    )


@router.patch("/{project_id}", response_model=ResponseModel[ProjectDetail])
def patch_project(
    project_id: str,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_project_service)
):
    """部分更新项目（推荐用于更新研究问题字段）"""
    project = service.update_project(project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return success_response(
        data=ProjectDetail.model_validate(project),
        message="项目更新成功"
    )


@router.delete("/{project_id}", response_model=ResponseModel)
def delete_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service)
):
    """删除项目"""
    success = service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return success_response(
        message="项目删除成功"
    )


# ============= 文件上传 API =============

@router.post("/upload", response_model=ResponseModel[UploadResponse])
async def upload_file(
    file: UploadFile = File(..., description="上传的文件"),
    project_id: Optional[str] = Query(None, description="所属项目ID"),
    doc_service: DocumentService = Depends(get_document_service)
):
    """
    上传文件（支持 PDF）

    .. deprecated::
        推荐使用 /api/v1/documents/upload 代替。
        该接口将在未来版本中移除。
    """
    # 读取文件内容
    file_content = await file.read()
    
    # 验证文件类型
    allowed_types = {'.pdf', '.txt', '.md', '.docx', '.csv'}
    file_extension = file.filename and file.filename.split('.')[-1].lower()
    if file_extension and f'.{file_extension}' not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，支持: {', '.join(allowed_types)}"
        )
    
    # 保存文档
    doc = doc_service.save_document(
        filename=file.filename,
        file_content=file_content,
        project_id=project_id
    )
    
    # 异步处理文档（这里先同步处理做演示）
    try:
        content = doc_service.extract_text_from_file(doc.file_path, doc.filename)
        doc_service.update_document_status(
            doc_id=doc.id,
            status="success",
            content=content,
            summary=content[:200] + "..." if len(content) > 200 else content
        )
    except Exception as e:
        doc_service.update_document_status(
            doc_id=doc.id,
            status="error",
            error_message=str(e)
        )
    
    return success_response(
        data=UploadResponse(
            file_id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status
        ),
        message="文件上传成功"
    )


@router.get("/{project_id}/documents", response_model=ResponseModel[PaginatedResponse[DocumentInfo]])
def list_documents(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    doc_service: DocumentService = Depends(get_document_service)
):
    """
    获取项目文档列表

    .. deprecated::
        推荐使用 /api/v1/documents?project_id={project_id} 代替。
        该接口将在未来版本中移除。
    """
    documents, total = doc_service.list_documents(
        project_id=project_id,
        page=page,
        page_size=page_size
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return success_response(
        data=PaginatedResponse(
            list=[DocumentInfo.model_validate(d) for d in documents],
            pagination=PageInfo(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages
            )
        ),
        message="获取文档列表成功"
    )


# ============= 假设查询 API =============

@router.get("/{project_id}/hypotheses", response_model=ResponseModel[List[HypothesisResponse]])
def list_project_hypotheses(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目的假设列表

    优先从 Hypothesis 表读取；若无数据则从最近一次 PipelineRun 的
    hypothesis_generation / hypothesis_review 阶段 output_data 中解析。
    """
    hypo_service = HypothesisService(db)

    # 1. 尝试从 Hypothesis 表读取
    hypotheses = hypo_service.get_hypotheses_by_project(project_id)

    if hypotheses:
        return success_response(
            data=[HypothesisResponse.model_validate(h) for h in hypotheses],
            message=f"获取假设列表成功，共 {len(hypotheses)} 条"
        )

    # 2. Fallback: 从最近一次成功 PipelineRun 的阶段输出中解析
    latest_run = (
        db.query(PipelineRun)
        .filter(
            PipelineRun.project_id == project_id,
            PipelineRun.status.in_([PipelineStatus.COMPLETED, PipelineStatus.FAILED])
        )
        .order_by(PipelineRun.created_at.desc())
        .first()
    )

    pipeline_hypotheses: List[HypothesisResponse] = []

    if latest_run:
        stage_names = ["hypothesis_generation", "hypothesis_review"]
        for stage_name in stage_names:
            stage_exec = (
                db.query(PipelineStageExecution)
                .filter(
                    PipelineStageExecution.pipeline_run_id == latest_run.id,
                    PipelineStageExecution.stage == stage_name
                )
                .first()
            )
            if stage_exec and stage_exec.output_data:
                output = stage_exec.output_data
                try:
                    items = output.get("hypotheses", [])
                    if isinstance(items, list):
                        for idx, item in enumerate(items):
                            pipeline_hypotheses.append(HypothesisResponse(
                                id=f"pipeline-{latest_run.id}-{stage_name}-{idx}",
                                project_id=project_id,
                                research_question=latest_run.research_question or "",
                                hypothesis=item.get("hypothesis", ""),
                                rationale=item.get("rationale", ""),
                                novelty=item.get("novelty", ""),
                                testability=item.get("testability", ""),
                                required_data=item.get("required_data", ""),
                                possible_method=item.get("possible_method", ""),
                                risk=item.get("risk", ""),
                                supporting_fact_ids=item.get("supporting_fact_ids", []),
                                evidence_level=item.get("evidence_level", "medium"),
                                status="draft",
                                priority=idx + 1 if idx + 1 <= 5 else 3,
                                confidence=0.7,
                                created_at=stage_exec.completed_at or latest_run.created_at,
                            ))
                except Exception as parse_err:
                    logger.warning(f"解析 Pipeline 阶段 {stage_name} 输出失败: {parse_err}")

    if pipeline_hypotheses:
        return success_response(
            data=pipeline_hypotheses,
            message=f"从 Pipeline 运行结果解析假设列表成功，共 {len(pipeline_hypotheses)} 条"
        )

    return success_response(
        data=[],
        message="暂无假设数据，请先运行 Pipeline"
    )


@router.post("/{project_id}/hypotheses/{hypothesis_id}/set-primary", response_model=ResponseModel[HypothesisResponse])
def set_primary_hypothesis(
    project_id: str,
    hypothesis_id: str,
    db: Session = Depends(get_db)
):
    """
    将指定假设设为主假设

    - **project_id**: 项目 ID
    - **hypothesis_id**: 假设 ID
    """
    hypo_service = HypothesisService(db)

    try:
        result = hypo_service.set_primary_hypothesis(project_id, hypothesis_id)
        if not result:
            raise HTTPException(status_code=404, detail="假设记录未找到")

        return success_response(
            data=HypothesisResponse.model_validate(result),
            message="设为主假设成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置主假设失败: {str(e)}")


# ============= 实验设计查询 API =============

@router.get("/{project_id}/experiment-designs", response_model=ResponseModel[List[ExperimentDesignDBResponse]])
def list_project_experiment_designs(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目的实验设计列表

    优先从 ExperimentDesign 表读取；若无数据则从最近一次 PipelineRun 的
    experiment_design 阶段 output_data 中解析。
    """
    experiment_service = ExperimentDesignService(db)

    designs = experiment_service.get_experiment_designs_by_project(project_id)

    if designs:
        return success_response(
            data=[ExperimentDesignDBResponse.model_validate(d) for d in designs],
            message=f"获取实验设计列表成功，共 {len(designs)} 条"
        )

    latest_run = (
        db.query(PipelineRun)
        .filter(
            PipelineRun.project_id == project_id,
            PipelineRun.status.in_([PipelineStatus.COMPLETED, PipelineStatus.FAILED])
        )
        .order_by(PipelineRun.created_at.desc())
        .first()
    )

    pipeline_designs: List[ExperimentDesignDBResponse] = []

    if latest_run:
        stage_exec = (
            db.query(PipelineStageExecution)
            .filter(
                PipelineStageExecution.pipeline_run_id == latest_run.id,
                PipelineStageExecution.stage == "experiment_design"
            )
            .first()
        )
        if stage_exec and stage_exec.output_data:
            output = stage_exec.output_data
            try:
                def safe_str(val, default=""):
                    if val is None:
                        return default
                    if isinstance(val, (list, dict)):
                        try:
                            return json.dumps(val, ensure_ascii=False)
                        except Exception:
                            return str(val)
                    return str(val)

                pipeline_designs.append(ExperimentDesignDBResponse(
                    id=f"pipeline-{latest_run.id}-experiment_design",
                    project_id=project_id,
                    hypothesis_id=output.get("hypothesis_id", "") or f"pipeline-run-{latest_run.id}",
                    hypothesis=output.get("hypothesis", ""),
                    methods=safe_str(output.get("methods", "")),
                    datasets=safe_str(output.get("datasets", "")),
                    source_data=safe_str(output.get("source_data", "")),
                    target_data=safe_str(output.get("target_data", "")),
                    baselines=safe_str(output.get("baselines", "")),
                    metrics=safe_str(output.get("metrics", "")),
                    experimental_steps=safe_str(output.get("experimental_steps", "")),
                    expected_results=safe_str(output.get("expected_results", "")),
                    limitations=safe_str(output.get("limitations", "")),
                    status="draft",
                    priority=1,
                    created_at=stage_exec.completed_at or latest_run.created_at,
                ))
            except Exception as parse_err:
                logger.warning(f"解析 Pipeline 阶段 experiment_design 输出失败: {parse_err}")

    if pipeline_designs:
        return success_response(
            data=pipeline_designs,
            message=f"从 Pipeline 运行结果解析实验设计成功，共 {len(pipeline_designs)} 条"
        )

    return success_response(
        data=[],
        message="暂无实验设计数据，请先运行 Pipeline 或生成实验设计"
    )
