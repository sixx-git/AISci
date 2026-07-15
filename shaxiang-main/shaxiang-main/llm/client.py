import json
import logging
import re
from typing import TypeVar, Type, Any
from openai import OpenAI

from config.settings import LLMConfig

T = TypeVar('T', bound='BaseModel')

logger = logging.getLogger(__name__)


class LLMClient:
    """统一的 LLM 客户端，支持 OpenAI 兼容 API（包括 DashScope）"""

    def __init__(self, config: LLMConfig):
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self.model = config.model
        self.default_temperature = config.temperature
        self.default_max_tokens = config.max_tokens

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        response_format: dict = None,
    ) -> str:
        """基础文本生成，统一把 content 规范成字符串。"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        content = self._normalize_message_content(getattr(message, "content", None))
        logger.info(
            f"LLM call: model={self.model}, "
            f"prompt_tokens={response.usage.prompt_tokens if response.usage else '?'}, "
            f"completion_tokens={response.usage.completion_tokens if response.usage else '?'}"
        )
        return content

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        output_schema: dict,
        temperature: float = None,
        max_retries: int = 3,
    ) -> dict:
        """使用 JSON Schema 约束生成结构化输出"""
        schema_instruction = (
            "\n\n你必须输出一个符合下列 JSON Schema 的「数据实例」对象。"
            "禁止输出 Schema 自身（不要出现顶层 type/properties/definitions/"
            "$defs/$ref 那套元描述）。只输出 JSON，不要 markdown：\n"
            + json.dumps(output_schema, ensure_ascii=False, indent=2)
        )
        full_system = system_prompt + schema_instruction

        for attempt in range(max_retries):
            try:
                raw = self.generate(
                    prompt=prompt,
                    system_prompt=full_system,
                    temperature=temperature or self.default_temperature,
                    response_format={"type": "json_object"},
                )
                parsed = self._extract_json_dict(raw)
                if not isinstance(parsed, dict):
                    raise ValueError(f"期望 JSON 对象，实际得到: {type(parsed).__name__}")
                if self._looks_like_json_schema(parsed):
                    raise ValueError(
                        "模型错误地输出了 JSON Schema 元描述，而不是数据实例"
                    )
                return parsed
            except (json.JSONDecodeError, ValueError, Exception) as e:
                logger.warning(f"结构化输出解析失败 (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                prompt += (
                    f"\n\n[注意] 上次输出无效: {e}。"
                    "请重新输出符合 Schema 的数据实例（含 title/description/hypothesis 等真实字段值），"
                    "不要再输出 type/properties 形式的 Schema。"
                )

        raise RuntimeError("LLM 结构化输出重试耗尽")

    def generate_to_model(
        self,
        prompt: str,
        system_prompt: str,
        model_class: Type[T],
        temperature: float = None,
    ) -> T:
        """生成结构化输出并映射到 Pydantic 模型"""
        schema = self._schema_for_llm(model_class)
        raw_dict = self.generate_structured(
            prompt=prompt,
            system_prompt=system_prompt,
            output_schema=schema,
            temperature=temperature,
        )
        return self._validate_model(model_class, raw_dict)

    @staticmethod
    def _normalize_message_content(content: Any) -> str:
        """兼容 str / list[content_part] / dict 等多种返回格式。"""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    text = part.get("text")
                    if text is None and isinstance(part.get("content"), str):
                        text = part["content"]
                    if text is not None:
                        parts.append(str(text))
                else:
                    text = getattr(part, "text", None)
                    if text is not None:
                        parts.append(str(text))
                    else:
                        parts.append(str(part))
            return "\n".join(parts)
        if isinstance(content, dict):
            if content.get("text") is not None:
                return str(content["text"])
            return json.dumps(content, ensure_ascii=False)
        return str(content)

    @classmethod
    def _extract_json_dict(cls, raw: str) -> dict:
        """从模型输出中提取 JSON 对象，兼容 markdown 围栏和 content-block 包装。"""
        text = (raw or "").strip()
        if not text:
            raise ValueError("模型返回空内容")

        # ```json ... ``` / ``` ... ```
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()

        # 截取最外层大括号
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end + 1]

        parsed = json.loads(text)

        # DashScope / 部分模型偶发包一层 {"type":"text","text":"{...}"}
        for _ in range(3):
            if not isinstance(parsed, dict):
                break
            if parsed.get("type") == "text" and "text" in parsed:
                inner = parsed["text"]
                if isinstance(inner, dict):
                    parsed = inner
                    continue
                if isinstance(inner, str):
                    parsed = cls._extract_json_dict(inner)
                    continue
            # 有些返回 {"content": "{...}"} / {"result": {...}}
            for key in ("content", "result", "data", "output"):
                if key in parsed and len(parsed) <= 3:
                    inner = parsed[key]
                    if isinstance(inner, dict):
                        parsed = inner
                        break
                    if isinstance(inner, str) and inner.strip().startswith("{"):
                        parsed = cls._extract_json_dict(inner)
                        break
            else:
                break
            continue

        if not isinstance(parsed, dict):
            raise ValueError(f"无法从模型输出提取 JSON 对象: {type(parsed).__name__}")
        return parsed

    @staticmethod
    def _looks_like_json_schema(obj: dict) -> bool:
        """判断模型是否把 JSON Schema 本身当成了回答。"""
        if not isinstance(obj, dict):
            return False
        # 典型 Schema 顶层键
        schema_keys = {"properties", "$defs", "definitions", "$schema", "items"}
        has_schema_shape = (
            obj.get("type") == "object"
            and isinstance(obj.get("properties"), dict)
            and schema_keys.intersection(obj.keys())
        )
        if not has_schema_shape:
            return False
        # 真正的 ExperimentPlan 等数据实例不会以 properties/$defs 为主
        data_hints = (
            "title", "description", "hypothesis", "methodology",
            "parameters", "script", "analysis_script", "script_params",
            "overall_assessment", "summary", "should_continue",
        )
        return not any(k in obj for k in data_hints)

    @staticmethod
    def _schema_for_llm(model_class: Type[T]) -> dict:
        """生成给 LLM 看的 schema，去掉仅由代码填充的字段要求。"""
        schema = model_class.model_json_schema()
        # iteration_number 由引擎写入，避免模型漏填导致校验失败
        props = schema.get("properties") or {}
        if "iteration_number" in props:
            props["iteration_number"]["default"] = 0
            props["iteration_number"]["description"] = (
                props["iteration_number"].get("description")
                or "迭代轮次，可填 0，系统会自动覆盖"
            )
        required = schema.get("required") or []
        if "iteration_number" in required:
            schema["required"] = [f for f in required if f != "iteration_number"]
        return schema

    @staticmethod
    def _validate_model(model_class: Type[T], raw_dict: dict) -> T:
        """兼容部分字段缺失：先严格校验，失败则补默认值再校验。"""
        if LLMClient._looks_like_json_schema(raw_dict):
            raise ValueError("收到 JSON Schema 元描述，无法映射为业务模型")
        try:
            return model_class.model_validate(raw_dict)
        except Exception as first_error:
            # 常见：模型漏填 iteration_number
            if "iteration_number" not in raw_dict:
                patched = dict(raw_dict)
                patched["iteration_number"] = 0
                try:
                    return model_class.model_validate(patched)
                except Exception:
                    pass
            raise first_error
