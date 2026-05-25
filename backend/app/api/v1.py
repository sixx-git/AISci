from fastapi import APIRouter
from app.api import research, chat, documents, projects, vector_search, agents

router = APIRouter()

router.include_router(projects.router)
router.include_router(research.router, prefix="/research", tags=["research"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(vector_search.router, prefix="/vector-search", tags=["vector-search"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
