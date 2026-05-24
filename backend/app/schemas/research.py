from pydantic import BaseModel
from typing import Optional, List


class ResearchRequest(BaseModel):
    topic: str
    keywords: Optional[List[str]] = None
    research_type: str = "literature_review"
    max_tokens: int = 4000


class ResearchResponse(BaseModel):
    success: bool
    research_id: str
    title: str
    content: str
    references: Optional[List[str]] = None
    execution_time: float
