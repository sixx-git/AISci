import time
import uuid
from sqlalchemy.orm import Session
from app.schemas.research import ResearchRequest, ResearchResponse
from app.models.research import ResearchProject
from app.services.llm_service import LLMService


class ResearchService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
    
    async def generate_research(self, request: ResearchRequest) -> ResearchResponse:
        start_time = time.time()
        research_id = str(uuid.uuid4())
        
        project = ResearchProject(
            id=research_id,
            topic=request.topic,
            keywords=",".join(request.keywords) if request.keywords else "",
            research_type=request.research_type,
            status="in_progress"
        )
        self.db.add(project)
        self.db.commit()
        
        prompt = self._build_research_prompt(request)
        response = await self.llm_service.generate(prompt, max_tokens=request.max_tokens)
        
        project.content = response
        project.status = "completed"
        project.execution_time = time.time() - start_time
        self.db.commit()
        
        return ResearchResponse(
            success=True,
            research_id=research_id,
            title=f"Research: {request.topic}",
            content=response,
            references=[],
            execution_time=time.time() - start_time
        )
    
    def _build_research_prompt(self, request: ResearchRequest) -> str:
        prompt = f"请为以下研究主题生成专业的学术研究报告：\n\n"
        prompt += f"主题：{request.topic}\n"
        if request.keywords:
            prompt += f"关键词：{', '.join(request.keywords)}\n"
        prompt += f"研究类型：{request.research_type}\n\n"
        prompt += "请提供详细的分析，包括背景、目的、方法、发现和结论。"
        return prompt
