from fastapi import APIRouter
from app.api import research, chat, documents, projects, vector_search, agents, reports, pipeline

router = APIRouter()

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(research.router, prefix="/research", tags=["research"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(vector_search.router, prefix="/vector-search", tags=["vector-search"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
