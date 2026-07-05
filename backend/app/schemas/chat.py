from pydantic import BaseModel
from typing import Optional, List


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    use_rag: bool = True
    project_id: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    session_id: str
    message: ChatMessage
    references: Optional[List[str]] = None
