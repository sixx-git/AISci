from fastapi import APIRouter
from app.api import (
    research,
    chat,
    documents,
    projects,
    vector_search,
    agents,
    reports,
    pipeline,
    literature,
    diagnose,
    prompts,
    human_loop,
    feedback,
    llm_config,
    skills,
    science_iteration,
    iterative_experiments,
    pingfenbiao_proxy,
)

router = APIRouter()

router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(iterative_experiments.router, tags=["iterative-experiments"])
router.include_router(pingfenbiao_proxy.router, tags=["pingfenbiao-proxy"])
router.include_router(research.router, prefix="/research", tags=["research"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(vector_search.router, prefix="/vector-search", tags=["vector-search"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
router.include_router(literature.router, prefix="/literature", tags=["literature"])
router.include_router(diagnose.router, prefix="/diagnose", tags=["diagnose"])
# 已淘汰 HTTP 面（服务层仍可能被 pipeline 内部调用）：
# datasets / multimodal / data_finder
router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
router.include_router(human_loop.router, prefix="/human-loop", tags=["human-loop"])
router.include_router(feedback.router, prefix="/feedback", tags=["feedback-hub"])
router.include_router(llm_config.router, prefix="/llm", tags=["llm-config"])
router.include_router(skills.router, prefix="/skills", tags=["skills"])
router.include_router(science_iteration.router, prefix="/science-iteration", tags=["science-iteration"])
