"""知识图谱 API"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
router = APIRouter()


class KgBuildRequest(BaseModel):
    project_id: str
    research_question: str = ""
    project_mode: Optional[str] = None
    literature_mining: Optional[Dict[str, Any]] = None
    knowledge_gap: Optional[Dict[str, Any]] = None
    report_sections: Optional[Dict[str, Any]] = None


class KgQueryRequest(BaseModel):
    project_id: str
    query: str = Field(..., description="自然语言图谱查询")
    education_level: str = Field(
        "undergraduate",
        description="primary|secondary|undergraduate|graduate|researcher",
    )
    retrieval_mode: str = Field(
        "hybrid",
        description="local|global|hybrid — LightRAG/GraphRAG 双级检索",
    )


class KgFeedbackRequest(BaseModel):
    project_id: str
    action: str = Field(..., description="verify|delete|update|add")
    target_type: str = Field("edge", description="node|edge")
    target_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class KgRebuildRequest(BaseModel):
    project_id: str
    research_question: str = ""
    project_mode: Optional[str] = None
    literature_mining: Optional[Dict[str, Any]] = None
    knowledge_gap: Optional[Dict[str, Any]] = None


class KgIncrementalRequest(BaseModel):
    project_id: str
    research_question: str = ""
    new_facts: Optional[List[Dict[str, Any]]] = None
    new_citation_map: Optional[List[Dict[str, Any]]] = None


def _resolve_mode(db: Session, project_id: str, override: Optional[str]) -> str:
    if override:
        return override
    project = ProjectService(db).get_project(project_id)
    if project:
        return getattr(project, "project_mode", None) or "general"
    return "general"


@router.get("/scenarios")
async def kg_scenarios(db: Session = Depends(get_db)):
    """参赛场景模板：领域、教育层级、检索模式说明"""
    service = get_knowledge_graph_service(db)
    return {"code": 200, "data": service.get_scenario_catalog(), "message": "success"}


@router.post("/build")
async def kg_build(body: KgBuildRequest, db: Session = Depends(get_db)):
    try:
        service = get_knowledge_graph_service(db)
        mode = _resolve_mode(db, body.project_id, body.project_mode)
        graph = await service.build_graph(
            project_id=body.project_id,
            literature_mining=body.literature_mining,
            knowledge_gap=body.knowledge_gap,
            report_sections=body.report_sections,
            project_mode=mode,
            research_question=body.research_question,
        )
        return {"code": 200, "data": graph, "message": "知识图谱构建完成"}
    except Exception as e:
        logger.error(f"kg build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}")
async def kg_get_project(project_id: str, db: Session = Depends(get_db)):
    service = get_knowledge_graph_service(db)
    graph = service.load_graph(project_id)
    if not graph:
        return {"code": 200, "data": None, "message": "暂无知识图谱，请先构建"}
    return {"code": 200, "data": graph, "message": "success"}


@router.post("/query")
async def kg_query(body: KgQueryRequest, db: Session = Depends(get_db)):
    try:
        service = get_knowledge_graph_service(db)
        result = await service.query_graph(
            body.project_id,
            body.query,
            education_level=body.education_level,
            retrieval_mode=body.retrieval_mode,
        )
        return {"code": 200, "data": result, "message": "查询完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incremental")
async def kg_incremental(body: KgIncrementalRequest, db: Session = Depends(get_db)):
    """LightRAG 风格增量更新：追加新文献事实而不全量重建"""
    try:
        service = get_knowledge_graph_service(db)
        result = await service.incremental_update(
            project_id=body.project_id,
            new_facts=body.new_facts,
            new_citation_map=body.new_citation_map,
            research_question=body.research_question,
        )
        return {"code": 200, "data": result, "message": "增量更新完成"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def kg_feedback(body: KgFeedbackRequest, db: Session = Depends(get_db)):
    try:
        service = get_knowledge_graph_service(db)
        feedback = {
            "action": body.action,
            "target_type": body.target_type,
            "target_id": body.target_id,
            "payload": body.payload or {},
        }
        result = await service.apply_feedback(body.project_id, feedback)
        return {"code": 200, "data": result, "message": "反馈已应用"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild")
async def kg_rebuild(body: KgRebuildRequest, db: Session = Depends(get_db)):
    try:
        service = get_knowledge_graph_service(db)
        mode = _resolve_mode(db, body.project_id, body.project_mode)
        graph = await service.rebuild_graph(
            project_id=body.project_id,
            literature_mining=body.literature_mining,
            knowledge_gap=body.knowledge_gap,
            project_mode=mode,
            research_question=body.research_question,
        )
        return {"code": 200, "data": graph, "message": "知识图谱已重建"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
