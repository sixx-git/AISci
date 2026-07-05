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
from app.core.async_utils import run_blocking
from app.core.response import ApiResponse, success, error
from app.services.literature_ingestion_service import LiteratureIngestionService
from app.services.literature_sources.bibtex_importer import BibTexParseError
from app.agents.problem_understanding_agent import get_problem_understanding_agent

import logging
logger = logging.getLogger(__name__)

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
    fallback: bool = Field(default=False, description="是否为 fallback 数据")


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


class DocumentActionRequest(BaseModel):
    project_id: str = Field(..., description="项目ID")
    document_id: str = Field(..., description="文献Document ID")
    auto_index: bool = Field(default=True, description="解析后是否自动构建向量索引")


class ArxivRecommendRequest(BaseModel):
    """从研究问题推荐 arXiv 文献"""
    project_id: str = Field(..., description="目标项目ID")
    research_question: str = Field(..., min_length=1, description="研究问题文本")
    max_results: int = Field(default=10, ge=1, le=100, description="最大推荐数")


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


@router.post("/recommend/arxiv")
async def recommend_arxiv_from_question(
    req: ArxivRecommendRequest,
    db: Session = Depends(get_db),
):
    """
    从研究问题自动检索 arXiv 文献

    流程：
      1. 调用 ProblemUnderstandingAgent 从研究问题中提取关键词
      2. 用关键词组合查询字符串搜索 arXiv
      3. （降级）如果关键词提取失败，直接用研究问题文本搜索
      4. 返回 arXiv 搜索结果（仅元数据，不下载 PDF）

    请求：
      { "project_id": "...", "research_question": "...", "max_results": 10 }

    响应：
      {
        "query_mode": "keyword" | "raw_question",
        "keywords": ["关键词1", "关键词2"],
        "total": N,
        "results": [ ArxivPaper, ... ]
      }
    """
    try:
        keywords: List[str] = []
        query_mode = "raw_question"
        search_query = req.research_question.strip()

        # 1. 尝试用 ProblemUnderstandingAgent 提取关键词
        try:
            agent = get_problem_understanding_agent()
            analysis = agent.analyze(research_question=req.research_question)
            if analysis.keywords and len(analysis.keywords) > 0:
                keywords = analysis.keywords
                # 使用 AND 组合关键词构建 arXiv query
                # arXiv 搜索语法: 用 AND 连接关键词可以提高精确度
                query_terms = [f"all:{kw}" for kw in keywords[:5]]  # 最多 5 个关键词
                search_query = " AND ".join(query_terms)
                query_mode = "keyword"
                logger.info(
                    f"从研究问题提取关键词: {keywords} → arXiv query: {search_query}"
                )
        except Exception as ex:
            logger.warning(f"关键词提取失败，将直接使用研究问题搜索: {ex}")

        # 2. 搜索 arXiv
        service = LiteratureIngestionService(db)
        results, fallback, warning = service.search_arxiv(
            query=search_query,
            max_results=req.max_results,
            start=0,
            sort_by="relevance",
        )

        return success(data={
            "query_mode": query_mode,
            "keywords": keywords,
            "original_question": req.research_question,
            "search_query": search_query,
            "total": len(results),
            "results": results,
            "fallback": fallback,
            "warning": warning,
        })
    except ValueError as e:
        return error(str(e), code=400)
    except RuntimeError as e:
        return error(str(e), code=502)
    except Exception as e:
        return error(f"arXiv 推荐失败: {str(e)}", code=500)
@router.post("/search/arxiv")
async def search_arxiv(
    req: ArxivSearchRequest,
    db: Session = Depends(get_db),
):
    """搜索 arXiv 文献"""
    try:
        service = LiteratureIngestionService(db)
        results, fallback, warning = service.search_arxiv(
            query=req.query,
            max_results=req.max_results,
            start=req.start,
            sort_by=req.sort_by,
        )
        return success(data={
            "query": req.query,
            "total": len(results),
            "results": results,
            "fallback": fallback,
            "warning": warning,
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
            fallback=req.fallback,
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


# ==================== arXiv PDF 下载 ====================

@router.post("/download-pdf")
async def download_arxiv_pdf(
    req: DocumentActionRequest,
    db: Session = Depends(get_db),
):
    """
    下载 arXiv 论文 PDF

    从 Document.pdf_url 下载 PDF 文件到本地存储。
    存储路径: storage/uploads/{project_id}/external/arxiv/{document_id}.pdf
    """
    try:
        service = LiteratureIngestionService(db)
        result = service.download_arxiv_pdf(
            project_id=req.project_id,
            document_id=req.document_id,
        )
        return success(
            data=result,
            message=f"PDF 下载完成 ({result['file_size']} bytes)",
        )
    except ValueError as e:
        return error(str(e), code=400)
    except RuntimeError as e:
        return error(str(e), code=502)
    except Exception as e:
        return error(f"PDF 下载异常: {str(e)}", code=500)


# ==================== 统一 PDF 解析 ====================

@router.post("/parse-document")
async def parse_document(
    req: DocumentActionRequest,
    db: Session = Depends(get_db),
):
    """
    统一 PDF 解析（任意来源：上传/arXiv/BibTeX 等）

    流程:
      1. 验证 PDF 文件存在
      2. 删除旧 Chunk（幂等重解析）
      3. DocumentParser 解析 PDF → 生成 Chunk
      4. 更新 import_status = parsed

    Project-level semantics:
      - 用户上传 PDF: source_type=upload, library_scope=personal, is_personal=true
      - arXiv PDF:     source_type=arxiv, library_scope=base,    is_personal=false
    """
    try:
        service = LiteratureIngestionService(db)
        result = await run_blocking(
            service.parse_document,
            req.project_id,
            req.document_id,
        )
        source_tag = f" (来源: {result.get('source_type', '?')})" if result.get('source_type') else ""
        return success(
            data=result,
            message=f"解析完成: {result['chunk_count']} 个切片{source_tag}",
        )
    except ValueError as e:
        return error(str(e), code=400)
    except RuntimeError as e:
        return error(str(e), code=502)
    except Exception as e:
        return error(f"解析异常: {str(e)}", code=500)


# ==================== 统一向量索引 ====================

@router.post("/index-document")
async def index_document(
    req: DocumentActionRequest,
    db: Session = Depends(get_db),
):
    """
    统一向量索引（任意来源）

    对项目级 Zvec 向量索引进行增量构建。
    LiteratureMiningAgent 不关心文献来源，仅按 project_id 检索。

    前置条件: 文档已解析（import_status = parsed）
    """
    try:
        service = LiteratureIngestionService(db)
        result = await run_blocking(
            service.index_document,
            req.project_id,
            req.document_id,
        )
        return success(
            data=result,
            message=f"向量索引完成: 新增 {result['index_added']} 条",
        )
    except ValueError as e:
        return error(str(e), code=400)
    except RuntimeError as e:
        return error(str(e), code=502)
    except Exception as e:
        return error(f"索引异常: {str(e)}", code=500)


# ==================== 组合: 解析 + 索引 ====================

@router.post("/parse-and-index")
async def parse_and_index(
    req: DocumentActionRequest,
    db: Session = Depends(get_db),
):
    """
    解析 PDF 并构建向量索引（组合调用）

    等价于 POST /parse-document → POST /index-document。
    auto_index=false 时仅执行解析，不索引。
    """
    try:
        service = LiteratureIngestionService(db)
        result = await run_blocking(
            service.parse_and_index,
            req.project_id,
            req.document_id,
            req.auto_index,
        )
        idx_msg = f"，索引新增 {result['index_added']} 条" if result.get('index_added') is not None else ""
        return success(
            data=result,
            message=f"解析完成: {result['chunk_count']} 个切片，状态={result['status']}{idx_msg}",
        )
    except ValueError as e:
        return error(str(e), code=400)
    except RuntimeError as e:
        return error(str(e), code=502)
    except Exception as e:
        return error(f"解析异常: {str(e)}", code=500)