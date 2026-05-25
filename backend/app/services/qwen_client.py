"""
Qwen/千问 API 调用封装
"""
import json
import logging
from typing import Dict, List, Optional, Any, Union
from functools import wraps
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai
from openai import APIError, APIConnectionError, APIStatusError, APITimeoutError

from app.core.config import get_settings

# 配置日志
logger = logging.getLogger(__name__)

# 初始化设置
settings = get_settings()


class QwenError(Exception):
    """Qwen API 基础异常"""
    pass


class QwenTimeoutError(QwenError):
    """超时异常"""
    pass


class QwenAPIError(QwenError):
    """API 调用异常"""
    pass


class QwenClient:
    """Qwen/千问 API 客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        初始化 Qwen 客户端
        
        Args:
            api_key: Qwen API Key，默认从配置读取
            base_url: API Base URL，默认从配置读取
            model: 模型名称，默认从配置读取
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key or settings.QWEN_API_KEY
        self.base_url = base_url or settings.QWEN_BASE_URL
        self.model = model or settings.QWEN_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            logger.warning("QWEN_API_KEY not set in environment")
        
        # 初始化 OpenAI 兼容客户端
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logger.info(f"QwenClient initialized with model: {self.model}")
    
    def _with_retry(func):
        """重试装饰器"""
        @wraps(func)
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((APIConnectionError, APITimeoutError))
        )
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except APIStatusError as e:
                logger.error(f"Qwen API Status Error: {e.status_code} - {e.message}")
                raise QwenAPIError(f"API Error: {e.status_code} - {e.message}") from e
            except APIConnectionError as e:
                logger.error(f"Qwen API Connection Error: {str(e)}")
                raise QwenAPIError(f"Connection Error: {str(e)}") from e
            except APITimeoutError as e:
                logger.error(f"Qwen API Timeout Error: {str(e)}")
                raise QwenTimeoutError(f"Timeout: {str(e)}") from e
            except APIError as e:
                logger.error(f"Qwen API Error: {str(e)}")
                raise QwenAPIError(f"API Error: {str(e)}") from e
            except Exception as e:
                logger.error(f"Unexpected Qwen API Error: {str(e)}")
                raise QwenAPIError(f"Unexpected Error: {str(e)}") from e
        return wrapper
    
    @_with_retry
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0
    ) -> str:
        """
        普通对话接口
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-2）
            max_tokens: 最大生成 token 数
            top_p: 核采样参数
            frequency_penalty: 频率惩罚
            presence_penalty: 存在惩罚
            
        Returns:
            模型回复文本
        """
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")
        
        messages: List[Dict[str, str]] = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        logger.debug(f"Calling Qwen chat with prompt: {prompt[:100]}...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty
            )
            
            content = response.choices[0].message.content
            
            if content is None:
                raise QwenAPIError("Empty response from Qwen API")
            
            logger.debug(f"Received Qwen response: {content[:100]}...")
            
            return content
            
        except Exception as e:
            logger.error(f"Qwen chat failed: {str(e)}")
            raise
    
    @_with_retry
    def structured_chat(
        self,
        prompt: str,
        schema_example: Optional[Union[Dict[str, Any], str]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        结构化输出接口，尽量返回 JSON
        
        Args:
            prompt: 用户输入
            schema_example: 期望的 JSON 格式示例（可选）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-2）
            max_tokens: 最大生成 token 数
            
        Returns:
            解析后的 JSON 字典
        """
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")
        
        # 构建增强的系统提示词
        structured_system_prompt = "你是一个有用的 AI 助手，请尽量以 JSON 格式回答问题。"
        
        if system_prompt:
            structured_system_prompt = f"{system_prompt}\n{structured_system_prompt}"
        
        if schema_example:
            # 如果提供了 schema example
            schema_str = json.dumps(schema_example, ensure_ascii=False, indent=2)
            structured_system_prompt += f"\n\n请按照以下 JSON 格式返回答案：\n```json\n{schema_str}\n```"
        
        # 增强用户提示词
        enhanced_prompt = f"""{prompt}

请以有效的 JSON 格式回答，不要添加任何 markdown 标记，只返回 JSON 本身。"""
        
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": structured_system_prompt},
            {"role": "user", "content": enhanced_prompt}
        ]
        
        logger.debug(f"Calling Qwen structured_chat with prompt: {prompt[:100]}...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            
            if content is None:
                raise QwenAPIError("Empty response from Qwen API")
            
            # 尝试解析 JSON
            try:
                # 清理可能的 markdown 标记
                cleaned_content = content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                elif cleaned_content.startswith("```"):
                    cleaned_content = cleaned_content[3:]
                
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                
                cleaned_content = cleaned_content.strip()
                
                result = json.loads(cleaned_content)
                logger.debug(f"Successfully parsed Qwen JSON response")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Qwen response as JSON: {str(e)}, falling back to raw content")
                # 如果解析失败，返回一个包含原始内容的字典
                return {"raw_response": content, "error": "JSON parse failed"}
                
        except Exception as e:
            logger.error(f"Qwen structured_chat failed: {str(e)}")
            raise
    
    @_with_retry
    def chat_with_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        多轮对话接口
        
        Args:
            messages: 消息列表，格式为 [{"role": "system|user|assistant", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            
        Returns:
            模型回复文本
        """
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")
        
        logger.debug(f"Calling Qwen chat_with_messages with {len(messages)} messages")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            
            if content is None:
                raise QwenAPIError("Empty response from Qwen API")
            
            return content
            
        except Exception as e:
            logger.error(f"Qwen chat_with_messages failed: {str(e)}")
            raise


# ==================== 便捷函数 ====================

# 全局单例
_qwen_client: Optional[QwenClient] = None


def get_qwen_client() -> QwenClient:
    """
    获取 Qwen 客户端单例
    
    Returns:
        QwenClient 实例
    """
    global _qwen_client
    if _qwen_client is None:
        _qwen_client = QwenClient()
    return _qwen_client


def qwen_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3
) -> str:
    """
    便捷的 Qwen 对话函数
    
    Args:
        prompt: 用户输入
        system_prompt: 系统提示词
        temperature: 温度参数
        
    Returns:
        模型回复文本
    """
    client = get_qwen_client()
    return client.chat(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature
    )


def qwen_structured_chat(
    prompt: str,
    schema_example: Optional[Union[Dict[str, Any], str]] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2
) -> Dict[str, Any]:
    """
    便捷的 Qwen 结构化输出函数
    
    Args:
        prompt: 用户输入
        schema_example: JSON 格式示例
        system_prompt: 系统提示词
        temperature: 温度参数
        
    Returns:
        解析后的 JSON 字典
    """
    client = get_qwen_client()
    return client.structured_chat(
        prompt=prompt,
        schema_example=schema_example,
        system_prompt=system_prompt,
        temperature=temperature
    )
