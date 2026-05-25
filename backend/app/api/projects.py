"""
项目 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional

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
from app.services.project_service import ProjectService, DocumentService

router = APIRouter(prefix="/api/projects", tags=["projects"])


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
    """更新项目"""
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
    """上传文件（支持 PDF）"""
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
    """获取项目文档列表"""
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
