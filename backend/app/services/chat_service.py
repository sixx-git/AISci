import uuid
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage as ChatMessageSchema
from app.models.chat import ChatSession, ChatMessage
from app.services.llm_service import LLMService
from app.services.vector_service import VectorService


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
        self.vector_service = VectorService()
    
    async def send_message(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        
        if not request.session_id:
            session = ChatSession(id=session_id)
            self.db.add(session)
            self.db.commit()
        
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=request.messages[-1].content
        )
        self.db.add(user_message)
        self.db.commit()
        
        references = []
        context = ""
        
        if request.use_rag:
            context, references = await self.vector_service.search(request.messages[-1].content)
        
        prompt = self._build_chat_prompt(request.messages, context)
        response = await self.llm_service.generate(prompt)
        
        assistant_message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=response,
            references=",".join(references) if references else None
        )
        self.db.add(assistant_message)
        self.db.commit()
        
        return ChatResponse(
            success=True,
            session_id=session_id,
            message=ChatMessageSchema(role="assistant", content=response),
            references=references if references else None
        )
    
    def _build_chat_prompt(self, messages, context: str) -> str:
        prompt = ""
        if context:
            prompt += f"参考信息：\n{context}\n\n"
        
        for msg in messages:
            prompt += f"{msg.role}: {msg.content}\n"
        
        prompt += "assistant: "
        return prompt
