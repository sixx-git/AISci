"""
文献库 API

支持：
- 查看可用文献来源
- arXiv 文献搜索
- 批量导入 arXiv 文献元数据
- 查询项目已导入文献
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.response import ApiResponse, success, error
from app.services.literature_ingestion_service import LiteratureIngestionService
from app.services.literature_sources.bibtex_importer import BibTexParseError

router = APIRouter(tags=["literature"])


# ==================== Pydantic Schemas ====================

class ArxivSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索关键词（支持 arXiv 查询语法）")
    max_results: int = Field(default=10, ge=1, le=100, description="最大返回数")
    start: int = Field(default=0, ge=0, description="起始偏移")
    sort_by: str = Field(default="relevance", description="排序: relevance / lastUpdatedDate / submittedDate")


class ArxivImportRequest(BaseModel):
    project_id: str = Field(..., description="目标项目ID")
    papers: List[dict] = Field(..., min_length=1, description="待导入论文元数据列表（来自 /search/arxiv 返回结果）")


class ProjectLiteratureQuery(BaseModel):
    project_id: str = Field(..., description="项目ID")
    source_type: Optional[str] = Field(None, description="来源筛选: upload / arxiv / bibtex ...")
    library_scope: Optional[str] = Field(None, description="范围筛选: base / project / personal")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class BibTexImportRequest(BaseModel):
    project_id: str = Field(..., description="目标项目ID")
    bibtex_text: str = Field(..., min_length=1, description="BibTeX 格式文本（支持多条目）")
    source_type: str = Field(default="google_scholar_import", description="来源类型: google_scholar_import / bibtex")


# ==================== API Endpoints ====================

@router.get("/sources")
async def list_sources():
    """获取可用的文献来源列表"""
    return success(data={
        "sources": [
            {
                "id": "arxiv",
                "name": "arXiv",
                "description": "arXiv 预印本论文库（搜索 + 导入元数据）",
                "features": ["search", "import_metadata"],
                "supports_pdf": False,
            },
            {
                "id": "bibtex",
                "name": "BibTeX",
                "description": "BibTeX 文献导入（手动粘贴或上传 .bib）",
                "features": ["import_metadata"],
                "supports_pdf": False,
            },
            {
                "id": "google_scholar_import",
                "name": "Google Scholar",
                "description": "Google Scholar BibTeX 导入（手动粘贴 .bib，不爬取网页）",
                "features": ["import_metadata"],
                "supports_pdf": False,
            },
            {
                "id": "upload",
                "name": "本地上传",
                "description": "用户手动上传 PDF 文献",
                "features": ["upload", "parse_pdf"],
                "supports_pdf": True,
            },
        ]
    })


@router.post("/search/arxiv")
async def search_arxiv(
    req: ArxivSearchRequest,
    db: Session = Depends(get_db),
):
    """搜索 arXiv 文献"""
    try:
        service = LiteratureIngestionService(db)
        results = service.search_arxiv(
            query=req.query,
            max_results=req.max_results,
            start=req.start,
            sort_by=req.sort_by,
        )
        return success(data={
            "query": req.query,
            "total": len(results),
            "results": results,
        })
    except ValueError as e:
        return error(str(e), code=400)
    except RuntimeError as e:
        return error(str(e), code=502)
    except Exception as e:
        return error(f"arXiv 搜索异常: {str(e)}", code=500)


@router.post("/import/arxiv")
async def import_arxiv(
    req: ArxivImportRequest,
    db: Session = Depends(get_db),
):
    """导入 arXiv 论文元数据到项目文献库"""
    try:
        service = LiteratureIngestionService(db)
        result = service.import_arxiv_papers(
            project_id=req.project_id,
            papers=req.papers,
        )
        return success(data=result, message=f"导入完成: 新增 {result['imported']}, 重复 {result['duplicates']}, 失败 {result['failed']}")
    except Exception as e:
        return error(f"导入失败: {str(e)}", code=500)


@router.get("/project/{project_id}")
async def get_project_literature(
    project_id: str,
    source_type: Optional[str] = Query(None, description="来源筛选"),
    library_scope: Optional[str] = Query(None, description="范围筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询项目已导入的文献列表"""
    try:
        service = LiteratureIngestionService(db)
        result = service.get_project_documents(
            project_id=project_id,
            source_type=source_type,
            library_scope=library_scope,
            page=page,
            page_size=page_size,
        )
        return success(data=result)
    except Exception as e:
        return error(str(e), code=500)


@router.post("/import/bibtex")
async def import_bibtex(
    req: BibTexImportRequest,
    db: Session = Depends(get_db),
):
    """
    导入 BibTeX 格式文献（Google Scholar / 其他来源导出）

    注意：
    - 本接口不爬取 Google Scholar，仅解析用户手动粘贴的 BibTeX 文本
    - 默认标记来源为 google_scholar_import
    - library_scope = project, is_personal = true
    """
    try:
        # 验证 source_type
        valid_types = {"google_scholar_import", "bibtex"}
        if req.source_type not in valid_types:
            return error(f"无效的 source_type: {req.source_type}，可选值: {', '.join(sorted(valid_types))}", code=400)

        service = LiteratureIngestionService(db)
        result = service.import_bibtex(
            project_id=req.project_id,
            bibtex_text=req.bibtex_text,
            source_type=req.source_type,
        )
        return success(
            data=result,
            message=f"BibTeX 导入完成: 新增 {result['imported']}, 重复 {result['duplicates']}, 失败 {result['failed']}",
        )
    except BibTexParseError as e:
        return error(f"BibTeX 解析失败: {str(e)}", code=400)
    except Exception as e:
        return error(f"BibTeX 导入失败: {str(e)}", code=500)