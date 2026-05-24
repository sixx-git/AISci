from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research_service import ResearchService

router = APIRouter()


@router.post("/generate", response_model=ResearchResponse)
async def generate_research(
    request: ResearchRequest,
    db: Session = Depends(get_db)
):
    service = ResearchService(db)
    try:
        result = await service.generate_research(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
