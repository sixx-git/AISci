import logging
import uuid
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage as ChatMessageSchema
from app.models.chat import ChatSession, ChatMessage
from app.services.llm_service import LLMService
from app.services.vector_store import get_vector_store, search_vector_store

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = LLMService()
    
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
            if request.project_id:
                context, references = self._search_project_literature(
                    request.project_id,
                    request.messages[-1].content,
                )
            else:
                context, references = await self._search_chat_vectors(
                    request.messages[-1].content,
                )
        
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

    def _search_project_literature(self, project_id: str, query: str, top_k: int = 5):
        """从项目 Zvec 索引检索文献片段（与文献库共用同一 Collection）。"""
        store = get_vector_store()
        if not store.has_index(project_id):
            return "", []

        try:
            results = search_vector_store(project_id, query, top_k=top_k, db=self.db)
        except ValueError as exc:
            logger.warning(
                "项目文献检索失败（将以无引用回答）project=%s err=%s",
                project_id,
                exc,
            )
            return "", []

        if not results:
            return "", []

        context_parts = []
        ref_set = set()
        for r in results:
            title = r.source_title or r.document_id
            page = f" p.{r.page_number}" if r.page_number else ""
            context_parts.append(f"[{title}{page}] {r.content}")
            ref_set.add(title)

        return "\n\n".join(context_parts), list(ref_set)

    async def _search_chat_vectors(self, query: str, top_k: int = 5):
        """从 Chat 专用 Zvec Collection 检索（无 project_id 时的 fallback）。"""
        from app.services.vector_service import VectorService

        service = VectorService()
        return await service.search(query, top_k=top_k)
    
    def _build_chat_prompt(self, messages, context: str) -> str:
        prompt = ""
        if context:
            prompt += f"参考信息：\n{context}\n\n"
        
        for msg in messages:
            prompt += f"{msg.role}: {msg.content}\n"
        
        prompt += "assistant: "
        return prompt
