from openai import OpenAI
from app.core.llm_runtime import (
    get_effective_api_key,
    get_effective_base_url,
    get_effective_model,
)


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=get_effective_api_key(),
            base_url=get_effective_base_url(),
        )

    async def generate(self, prompt: str, max_tokens: int = 2000, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=get_effective_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content
