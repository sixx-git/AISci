"""
向量搜索 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.response import ApiResponse, success, error
from app.services.vector_store import (
    get_vector_store,
    add_chunks_to_vector_store,
    search_vector_store,
    SearchResult
)

router = APIRouter(prefix="/vector-search", tags=["vector-search"])


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索查询文本")
    top_k: int = Field(5, ge=1, le=50, description="返回结果数量")


class SearchResultItem(BaseModel):
    """搜索结果项"""
    chunk_id: str
    content: str
    document_id: str
    document_title: Optional[str] = None
    document_filename: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    similarity: float
    score: float


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResultItem]
    total: int


class IndexStatsResponse(BaseModel):
    """索引统计响应"""
    project_id: str
    exists: bool
    chunk_count: int
    dimension: Optional[int] = None
    index_type: Optional[str] = None
    embedding_model: Optional[str] = None


class AddChunksResponse(BaseModel):
    """添加 Chunks 响应"""
    added_count: int


@router.post("/search/{project_id}", response_model=ApiResponse[SearchResponse])
async def vector_search(
    project_id: str,
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    向量搜索
    
    在指定项目的向量索引中搜索相关文献切片
    """
    try:
        results = search_vector_store(
            project_id=project_id,
            query=request.query,
            top_k=request.top_k,
            db=db
        )
        
        result_items = [
            SearchResultItem(
                chunk_id=r.chunk_id,
                content=r.content,
                document_id=r.document_id,
                document_title=r.document_title,
                document_filename=r.document_filename,
                start_page=r.start_page,
                end_page=r.end_page,
                similarity=r.similarity,
                score=r.score
            )
            for r in results
        ]
        
        return success(
            SearchResponse(
                results=result_items,
                total=len(result_items)
            ),
            message=f"找到 {len(result_items)} 个相关结果"
        )
    except Exception as e:
        return error(str(e))


@router.post("/index/{project_id}/add-chunks", response_model=ApiResponse[AddChunksResponse])
async def index_chunks(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    添加项目 Chunks 到向量索引
    
    将项目的所有未向量化的文献切片添加到向量索引中
    """
    try:
        added_count = add_chunks_to_vector_store(project_id, db)
        
        return success(
            AddChunksResponse(
                added_count=added_count
            ),
            message=f"成功添加 {added_count} 个切片到向量索引"
        )
    except Exception as e:
        return error(str(e))


@router.get("/index/{project_id}/stats", response_model=ApiResponse[IndexStatsResponse])
async def get_index_stats(
    project_id: str
):
    """
    获取项目向量索引统计信息
    """
    try:
        store = get_vector_store()
        stats = store.get_project_stats(project_id)
        
        return success(
            IndexStatsResponse(
                project_id=stats["project_id"],
                exists=stats["exists"],
                chunk_count=stats["chunk_count"],
                dimension=stats.get("dimension"),
                index_type=stats.get("index_type"),
                embedding_model=stats.get("embedding_model")
            )
        )
    except Exception as e:
        return error(str(e))


@router.delete("/index/{project_id}", response_model=ApiResponse)
async def delete_index(
    project_id: str
):
    """
    删除项目向量索引
    """
    try:
        store = get_vector_store()
        success_flag = store.delete_project_index(project_id)
        
        if success_flag:
            return success(message="索引删除成功")
        else:
            return error("索引删除失败", code=500)
    except Exception as e:
        return error(str(e))
