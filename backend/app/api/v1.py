from fastapi import APIRouter
from app.api import research, chat, documents, projects

router = APIRouter()

router.include_router(projects.router)
router.include_router(research.router, prefix="/research", tags=["research"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
