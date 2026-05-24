from openai import OpenAI
from app.core.config import get_settings

settings = get_settings()


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL
        )
    
    async def generate(self, prompt: str, max_tokens: int = 2000, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=settings.QWEN_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            **kwargs
        )
        return response.choices[0].message.content
