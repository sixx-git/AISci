"""
向量搜索 API
POST /api/v1/vector-search/build  — 构建项目向量索引
POST /api/v1/vector-search/search — 搜索项目向量索引
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.response import ApiResponse, success, error
from app.services.vector_store import (
    get_vector_store,
    build_vector_index,
    search_vector_store,
    SearchResult,
)

router = APIRouter(tags=["vector-search"])


# ─────────── 请求模型 ───────────

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索查询文本", min_length=1)
    top_k: int = Field(5, ge=1, le=50, description="返回结果数量")


# ─────────── 响应模型 ───────────

class SearchResultItem(BaseModel):
    """搜索结果项"""
    chunk_id: str = Field(..., description="切片 ID")
    document_id: str = Field(..., description="所属文档 ID")
    content: str = Field(..., description="切片文本内容")
    page_number: Optional[int] = Field(None, description="所在页码")
    source_title: Optional[str] = Field(None, description="来源文档标题")
    similarity_score: float = Field(..., description="相似度分数")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResultItem] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="结果总数")


class BuildResponse(BaseModel):
    """构建索引响应"""
    project_id: str = Field(..., description="项目 ID")
    added_count: int = Field(..., description="新增索引的切片数")
    total_count: int = Field(..., description="项目当前索引总数")


class IndexStatsResponse(BaseModel):
    """索引统计响应"""
    project_id: str
    exists: bool
    chunk_count: int
    dimension: Optional[int] = None
    embedding_model: Optional[str] = None
    index_file: Optional[str] = None
    mapping_file: Optional[str] = None


# ─────────── 构建索引 ───────────

@router.post("/build", response_model=ApiResponse[BuildResponse])
async def build_index(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db)
):
    """
    构建项目向量索引

    查询 project_id 下所有已解析文档的 Chunk，
    使用 embedding 模型生成向量，存入 FAISS 索引。
    """
    try:
        # 检查是否有 Chunk
        from app.models.project import Chunk, Document, DocumentStatus
        chunk_count = (
            db.query(Chunk)
            .join(Document, Chunk.document_id == Document.id)
            .filter(Chunk.project_id == project_id)
            .filter(Document.status == DocumentStatus.PROCESSED)
            .count()
        )

        if chunk_count == 0:
            return error(f"项目 {project_id} 没有已解析的Chunk，请先上传并解析文档", code=1)

        added_count = build_vector_index(project_id, db)

        store = get_vector_store()
        total = len(store._mappings.get(project_id, []))

        return success(
            BuildResponse(
                project_id=project_id,
                added_count=added_count,
                total_count=total,
            ),
            message=f"构建成功，新增 {added_count} 条，当前共 {total} 条切片",
        )

    except Exception as e:
        return error(str(e), code=1)


# ─────────── 搜索 ───────────

@router.post("/search", response_model=ApiResponse[SearchResponse])
async def vector_search(
    request: SearchRequest,
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db)
):
    """
    向量搜索

    在指定项目的 FAISS 索引中检索与 query 最相似的 Chunk。
    """
    try:
        store = get_vector_store()

        if not store.has_index(project_id):
            return error(f"项目 {project_id} 尚未构建向量索引，请先调用 /vector-search/build", code=1)

        results = search_vector_store(
            project_id=project_id,
            query=request.query,
            top_k=request.top_k,
            db=db,
        )

        items = [
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                page_number=r.page_number,
                source_title=r.source_title,
                similarity_score=r.similarity_score,
            )
            for r in results
        ]

        return success(
            SearchResponse(results=items, total=len(items)),
            message=f"找到 {len(items)} 个相关结果",
        )

    except ValueError as e:
        return error(str(e), code=1)
    except Exception as e:
        return error(str(e), code=1)


# ─────────── 统计 ───────────

@router.get("/index/{project_id}/stats", response_model=ApiResponse[IndexStatsResponse])
async def get_index_stats(project_id: str):
    """获取项目向量索引统计信息"""
    try:
        store = get_vector_store()
        stats = store.get_project_stats(project_id)
        return success(IndexStatsResponse(**stats))
    except Exception as e:
        return error(str(e), code=1)


# ─────────── 删除 ───────────

@router.delete("/index/{project_id}", response_model=ApiResponse)
async def delete_index(project_id: str):
    """删除项目向量索引"""
    try:
        store = get_vector_store()
        ok = store.delete_project_index(project_id)
        if ok:
            return success(message="索引删除成功")
        return error("索引删除失败", code=1)
    except Exception as e:
        return error(str(e), code=1)