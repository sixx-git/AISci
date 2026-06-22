from fastapi import APIRouter
from app.api import research, chat, documents, projects, vector_search, agents, reports, pipeline, literature, diagnose, datasets, data_finder, kg, prompts, human_loop, multimodal, feedback, llm_config

router = APIRouter()

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(research.router, prefix="/research", tags=["research"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(vector_search.router, prefix="/vector-search", tags=["vector-search"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
router.include_router(literature.router, prefix="/literature", tags=["literature"])
router.include_router(diagnose.router, prefix="/diagnose", tags=["diagnose"])
router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
router.include_router(multimodal.router, prefix="/multimodal", tags=["multimodal"])
router.include_router(data_finder.router, prefix="/data-finder", tags=["data-finder"])
router.include_router(kg.router, prefix="/kg", tags=["knowledge-graph"])
router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
router.include_router(human_loop.router, prefix="/human-loop", tags=["human-loop"])
router.include_router(feedback.router, prefix="/feedback", tags=["feedback-hub"])
router.include_router(llm_config.router, prefix="/llm", tags=["llm-config"])
