"""
Qwen/千问 API 调用封装

增强功能：
- structured_chat 严格 JSON 输出 + 自动修复 + AgentOutputParseError
- 每次调用自动记录日志（model_name, temperature, prompt_version, input, output, duration）
- 所有 API Key 从 .env 读取，不硬编码
"""
import json
import re
import time
import logging
from typing import Dict, List, Optional, Any, Union
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import openai
from openai import APIError, APIConnectionError, APIStatusError, APITimeoutError

from app.core.config import get_settings
from app.core.llm_runtime import (
    get_effective_api_key,
    get_effective_base_url,
    get_effective_model,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def build_dashscope_http_client(timeout: float = 180.0) -> httpx.Client:
    """构建访问百炼的 httpx Client；默认强制 IPv4，规避 IPv6 SSL EOF。"""
    timeout_cfg = httpx.Timeout(timeout)
    force_ipv4 = bool(getattr(settings, "QWEN_FORCE_IPV4", True))
    if force_ipv4:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        logger.info("Qwen HTTP client: force IPv4 (QWEN_FORCE_IPV4=true)")
        return httpx.Client(timeout=timeout_cfg, transport=transport)
    return httpx.Client(timeout=timeout_cfg)


# ==================== 自定义异常 ====================

class QwenError(Exception):
    """Qwen API 基础异常"""
    pass


class QwenTimeoutError(QwenError):
    """超时异常"""
    pass


class QwenAPIError(QwenError):
    """API 调用异常"""
    pass


class AgentOutputParseError(QwenError):
    """Agent 输出 JSON 解析失败异常（不允许降级为 raw_response）"""
    def __init__(self, message: str, raw_output: str = "", repair_attempted: bool = False):
        super().__init__(message)
        self.raw_output = raw_output
        self.repair_attempted = repair_attempted


# ==================== 调用日志 ====================

@dataclass
class CallLog:
    """单次调用日志"""
    timestamp: str = ""
    model_name: str = ""
    temperature: float = 0.2
    prompt_version: str = ""
    input: str = ""
    output: str = ""
    duration_ms: int = 0
    success: bool = True
    error: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# 模块级调用日志存储
_call_logs: List[CallLog] = []


def get_call_logs() -> List[CallLog]:
    """获取所有调用日志"""
    return list(_call_logs)


def clear_call_logs() -> None:
    """清空调用日志"""
    _call_logs.clear()


def _truncate(text: str, max_len: int = 500) -> str:
    """截断文本，用于日志记录"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...[truncated]"


def _format_api_status_error(status_code: int, message: str) -> str:
    """将 DashScope/OpenAI 兼容 API 错误转为更易读的中文提示。"""
    raw = str(message or "")
    lower = raw.lower()
    if status_code == 401 or "invalid_api_key" in lower or "incorrect api key" in lower:
        return (
            "千问 API 密钥无效或未授权 (401)。请检查 backend/.env 中的 QWEN_API_KEY，"
            "或在「设置 → LLM 配置」更新密钥。"
        )
    if status_code == 403 and "allocationquota.freetieronly" in lower:
        return (
            "当前 API Key 在「仅使用免费额度」模式下，所选模型已无免费额度 (403)。"
            "换模型不一定能恢复——不同模型额度独立；请用「测试连接」确认可用模型，"
            "或在百炼控制台开通按量付费并关闭「仅免费」限制。"
        )
    if status_code == 403 and (
        "quota" in lower
        or "free" in lower
        or "exhausted" in lower
        or "额度" in raw
        or "配额" in raw
    ):
        return (
            "千问 API 额度不足 (403)。请在百炼控制台查看该模型的剩余额度，"
            "或开通按量付费；也可尝试切换到当前 Key 仍有额度的其他模型。"
        )
    if status_code == 429 or "rate limit" in lower or "throttl" in lower:
        return (
            "千问 API 请求过于频繁或触发限流 (429)。请稍后重试，或切换到更轻量的模型。"
        )
    return f"API Error: {status_code} - {raw}"


# ==================== JSON 修复工具 ====================

def _safe_json_loads(text: str) -> dict:
    """尝试解析 JSON，但不做修复（先只清理 markdown 标记）"""
    cleaned = text.strip()
    # 移除 markdown 代码块标记
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def _try_extract_json_block(text: str) -> Optional[str]:
    """尝试从混合文本中提取 JSON 块"""
    # 尝试匹配 ```json ... ```
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        return m.group(1).strip()

    # 尝试匹配第一个 { 到最后一个 }
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1]

    return None


def _fill_missing_braces(json_str: str) -> str:
    """补齐缺失的大括号，用于修复截断的 JSON"""
    open_braces = json_str.count('{') - json_str.count('}')
    open_brackets = json_str.count('[') - json_str.count(']')
    # 补齐尾部引号（找到最后一个未闭合的字符串值）
    in_string = False
    escape_next = False
    for ch in json_str:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        json_str += '"'
    # 补齐括号
    json_str += ']' * open_brackets
    json_str += '}' * open_braces
    return json_str


def _repair_json(raw_text: str) -> dict:
    """
    多层次 JSON 修复策略

    策略：
    1. 直接解析（清理 markdown 标记后）
    2. 从混合文本中提取 JSON 块
    3. 修复尾部逗号（trailing commas）
    4. 补齐截断的括号
    5. 修复常见 LLM 输出问题（单引号 → 双引号、None → null 等）
    """
    best_error = None

    # 策略 1：直接解析
    try:
        return _safe_json_loads(raw_text)
    except json.JSONDecodeError as e:
        best_error = e

    # 策略 2：从混合文本中提取 JSON 块
    extracted = _try_extract_json_block(raw_text)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass
        # 对提取的块也做修复
        candidates = [extracted]
    else:
        candidates = [raw_text]

    # 准备多种修复后的候选文本
    for candidate in list(candidates):
        # 策略 3a：移除 JSON 字符串中的非法控制字符
        ctrl_stripped = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", candidate)
        if ctrl_stripped != candidate:
            candidates.append(ctrl_stripped)

        # 策略 3：移除尾部逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', candidate)
        if fixed != candidate:
            candidates.append(fixed)

        # 策略 4：补齐截断的括号
        filled = _fill_missing_braces(candidate)
        if filled != candidate:
            candidates.append(filled)

        # 策略 5a：Python None → JSON null
        py_fixed = re.sub(r':\s*None\s*([,}\]])', r': null\1', candidate)
        if py_fixed != candidate:
            candidates.append(py_fixed)

        # 策略 5b：True/False → true/false
        py_fixed = re.sub(r':\s*True\s*([,}\]])', r': true\1', candidate)
        if py_fixed != candidate:
            candidates.append(py_fixed)
        py_fixed = re.sub(r':\s*False\s*([,}\]])', r': false\1', candidate)
        if py_fixed != candidate:
            candidates.append(py_fixed)

        # 策略 5c：单引号 → 双引号（只处理键值对中的单引号）
        try:
            # 尝试 ast.literal_eval 作为最后一招（处理 Python dict 格式）
            import ast
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass

    # 对所有候选文本尝试解析
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # 所有策略都失败，抛出异常
    raise best_error if best_error else json.JSONDecodeError(
        "All repair strategies failed", raw_text, 0
    )


# ==================== QwenClient ====================

class QwenClient:
    """Qwen/千问 API 客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 180,
        max_retries: int = 2
    ):
        self.api_key = api_key or get_effective_api_key()
        self.base_url = base_url or get_effective_base_url()
        self._pinned_model = model  # 测试注入；None 表示每次调用读取运行时配置
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.api_key:
            logger.warning("QWEN_API_KEY not set in environment")

        self.client = self._create_openai_client()

        logger.info(f"QwenClient initialized with model: {self.model}")

    @property
    def model(self) -> str:
        """每次调用使用当前生效模型（支持设置页切换后立即生效）。"""
        if self._pinned_model:
            return self._pinned_model
        return get_effective_model()

    def _create_openai_client(self):
        try:
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                http_client=build_dashscope_http_client(timeout=float(self.timeout)),
            )
            return client
        except Exception as e:
            from importlib.metadata import version as pkg_version

            logger.error(
                f"OpenAI client 初始化失败:\n"
                f"  openai version: {pkg_version('openai')}\n"
                f"  httpx version: {pkg_version('httpx')}\n"
                f"  base_url: {self.base_url}\n"
                f"  model: {self.model}\n"
                f"  error: {type(e).__name__}: {e}"
            )
            raise

    # ==================== 内部工具 ====================

    def _with_retry(func):
        """重试装饰器 —— 使用 ThreadPoolExecutor 实现硬超时 + 重试"""
        import concurrent.futures

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            timeout = getattr(self, 'timeout', 180)
            max_attempts = 3
            last_error = None

            for attempt in range(1, max_attempts + 1):
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(func, self, *args, **kwargs)

                def _shutdown_executor(wait: bool) -> None:
                    try:
                        executor.shutdown(wait=wait, cancel_futures=not wait)
                    except TypeError:
                        executor.shutdown(wait=wait)

                try:
                    result = future.result(timeout=timeout)
                    _shutdown_executor(wait=True)
                    return result
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    _shutdown_executor(wait=False)
                    last_error = QwenTimeoutError(
                        f"LLM call exceeded {timeout}s total (attempt {attempt}/{max_attempts})"
                    )
                    logger.warning(
                        f"[LLM超时] {func.__name__} 超过 {timeout}s 总时限 "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    if attempt < max_attempts:
                        wait_s = min(2 ** attempt, 10)
                        logger.info(f"[LLM重试] 等待 {wait_s}s 后重试...")
                        time.sleep(wait_s)
                    continue
                except APIStatusError as e:
                    _shutdown_executor(wait=False)
                    logger.error(f"Qwen API Status Error: {e.status_code} - {e.message}")
                    raise QwenAPIError(_format_api_status_error(e.status_code, str(e.message))) from e
                except APIConnectionError as e:
                    _shutdown_executor(wait=False)
                    cause = e.__cause__ or e.__context__
                    detail = str(cause).strip() if cause else str(e).strip()
                    last_error = QwenAPIError(
                        f"Connection Error: {detail or str(e)} "
                        f"[base_url={self.base_url}]"
                    )
                    logger.warning(
                        f"Qwen API Connection Error: {detail or str(e)} "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    if attempt < max_attempts:
                        wait_s = min(2 ** attempt, 10)
                        logger.info(f"[LLM重试] 等待 {wait_s}s 后重试...")
                        time.sleep(wait_s)
                    continue
                except APITimeoutError as e:
                    _shutdown_executor(wait=False)
                    last_error = QwenTimeoutError(f"Timeout: {str(e)}")
                    logger.warning(
                        f"Qwen API Timeout Error: {str(e)} "
                        f"(attempt {attempt}/{max_attempts})"
                    )
                    if attempt < max_attempts:
                        wait_s = min(2 ** attempt, 10)
                        logger.info(f"[LLM重试] 等待 {wait_s}s 后重试...")
                        time.sleep(wait_s)
                    continue
                except AgentOutputParseError:
                    # JSON 解析失败已在 structured_chat 内做过一次重调；
                    # 此处原样抛出，避免被包装成「Unexpected Error」掩盖根因。
                    _shutdown_executor(wait=False)
                    raise
                except QwenError:
                    _shutdown_executor(wait=False)
                    raise
                except APIError as e:
                    _shutdown_executor(wait=False)
                    logger.error(f"Qwen API Error: {str(e)}")
                    raise QwenAPIError(f"API Error: {str(e)}") from e
                except Exception as e:
                    _shutdown_executor(wait=False)
                    logger.error(f"Unexpected Qwen API Error: {str(e)}")
                    raise QwenAPIError(f"Unexpected Error: {str(e)}") from e

            raise last_error or QwenTimeoutError("LLM call failed after all retries")

        return wrapper

    def _log_call(
        self,
        model_name: str,
        temperature: float,
        prompt_version: str,
        input_text: str,
        output_text: str,
        duration_ms: int,
        success: bool,
        error: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0
    ):
        """记录一次调用"""
        log_entry = CallLog(
            timestamp=datetime.utcnow().isoformat() + "Z",
            model_name=model_name,
            temperature=temperature,
            prompt_version=prompt_version,
            input=_truncate(input_text),
            output=_truncate(output_text),
            duration_ms=duration_ms,
            success=success,
            error=error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        _call_logs.append(log_entry)
        if success:
            logger.info(
                f"[QwenCall] model={model_name} temp={temperature} "
                f"version={prompt_version} duration={duration_ms}ms "
                f"tokens={total_tokens} OK"
            )
        else:
            logger.warning(
                f"[QwenCall] model={model_name} temp={temperature} "
                f"version={prompt_version} duration={duration_ms}ms FAILED: {error}"
            )

    # ==================== 普通对话 ====================

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
        """普通对话接口"""
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Calling Qwen chat with prompt: {prompt[:100]}...")
        t0 = time.time()

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

            duration_ms = int((time.time() - t0) * 1000)
            usage = response.usage
            self._log_call(
                self.model, temperature, "", prompt, content, duration_ms, True,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )
            logger.debug(f"Received Qwen response: {content[:100]}...")
            return content

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            self._log_call(self.model, temperature, "", prompt, "", duration_ms, False, str(e))
            raise

    # ==================== 结构化对话（核心增强） ====================

    @_with_retry
    def structured_chat(
        self,
        prompt: str,
        schema_example: Optional[Union[Dict[str, Any], str]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        prompt_version: str = ""
    ) -> Dict[str, Any]:
        """
        结构化输出接口 —— 强制返回 JSON

        增强点：
        - JSON 解析失败时自动尝试修复
        - 修复仍失败时再调一次 LLM（更强 JSON 约束）
        - 最终失败抛出 AgentOutputParseError（绝不返回 raw_response）
        - 自动记录调用日志

        Args:
            prompt: 用户输入
            schema_example: 期望的 JSON 格式示例
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            prompt_version: Prompt 模板版本标识（用于日志追踪）

        Returns:
            解析后的 JSON 字典

        Raises:
            AgentOutputParseError: JSON 解析失败（含自动修复与一次重调）
        """
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")

        # 构建系统提示词（强调 JSON 输出）
        structured_system = (
            "你是一个 JSON 输出助手。你必须只返回合法的 JSON 对象，不要包含任何解释、"
            "markdown 标记或额外文本。你的整个响应必须是可被 json.loads() 直接解析的。"
        )
        if system_prompt:
            structured_system = f"{system_prompt}\n\n{structured_system}"

        if schema_example:
            schema_str = json.dumps(schema_example, ensure_ascii=False, indent=2)
            structured_system += (
                f"\n\n请严格按照以下 JSON Schema 返回，不要增加或省略字段：\n```json\n{schema_str}\n```"
            )

        # 用户 prompt 增强
        enhanced_prompt = f"{prompt}\n\n只返回 JSON，不要任何解释。"

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": structured_system},
            {"role": "user", "content": enhanced_prompt}
        ]

        logger.debug(
            f"Calling Qwen structured_chat: prompt={prompt[:100]}... "
            f"schema_keys={list(schema_example.keys()) if isinstance(schema_example, dict) else 'N/A'}"
        )

        t0 = time.time()
        token_pt = token_ct = token_tt = 0

        def _invoke(msgs: List[Dict[str, str]], temp: float) -> str:
            nonlocal token_pt, token_ct, token_tt
            logger.info(
                f"[LLM] structured_chat 调用 model={self.model} "
                f"msgs={len(msgs)} max_tokens={max_tokens} temp={temp}"
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                temperature=temp,
                max_tokens=max_tokens or 8192,
                timeout=self.timeout,
            )
            content = response.choices[0].message.content
            usage_data = response.usage
            if usage_data:
                token_pt += usage_data.prompt_tokens or 0
                token_ct += usage_data.completion_tokens or 0
                token_tt += usage_data.total_tokens or 0
            return content if content is not None else ""

        def _try_parse(raw: str) -> tuple[Optional[dict], Optional[Exception]]:
            if not (raw or "").strip():
                return None, json.JSONDecodeError(
                    "Expecting value: empty model output", raw or "", 0
                )
            try:
                return _safe_json_loads(raw), None
            except json.JSONDecodeError as e1:
                try:
                    return _repair_json(raw), None
                except json.JSONDecodeError:
                    return None, e1

        raw_content = ""
        try:
            raw_content = _invoke(messages, temperature)
        except (QwenAPIError, QwenTimeoutError) as e:
            duration_ms = int((time.time() - t0) * 1000)
            self._log_call(
                self.model, temperature, prompt_version, prompt, "", duration_ms, False, str(e)
            )
            raise

        json_obj, first_error = _try_parse(raw_content)
        if json_obj is not None:
            duration_ms = int((time.time() - t0) * 1000)
            self._log_call(
                self.model,
                temperature,
                prompt_version,
                prompt,
                json.dumps(json_obj, ensure_ascii=False),
                duration_ms,
                True,
                prompt_tokens=token_pt,
                completion_tokens=token_ct,
                total_tokens=token_tt,
            )
            return json_obj

        # ──── 模型输出无法解析：自动再跑一次 LLM ────
        preview = (raw_content or "").strip()
        preview = preview[:400] if preview else "(空输出)"
        logger.warning(
            "structured_chat JSON 解析失败，自动重调 LLM 一次: %s | preview=%r",
            first_error,
            preview[:120],
        )
        retry_messages: List[Dict[str, str]] = list(messages) + [
            {"role": "assistant", "content": preview},
            {
                "role": "user",
                "content": (
                    "上一次输出不是合法 JSON（可能为空、含解释文字或 markdown 代码块）。"
                    "请重新输出：只返回一个完整的 JSON 对象，"
                    "不要 markdown 代码块，不要任何解释或前后缀文字。"
                ),
            },
        ]
        retry_temp = min(float(temperature), 0.1)
        try:
            raw_retry = _invoke(retry_messages, retry_temp)
        except (QwenAPIError, QwenTimeoutError) as e:
            duration_ms = int((time.time() - t0) * 1000)
            self._log_call(
                self.model,
                temperature,
                prompt_version,
                prompt,
                raw_content,
                duration_ms,
                False,
                f"JSON parse failed then retry API error: {e}",
                prompt_tokens=token_pt,
                completion_tokens=token_ct,
                total_tokens=token_tt,
            )
            raise AgentOutputParseError(
                message=(
                    f"Agent 输出无法解析为合法 JSON。原始错误: {first_error}。"
                    f"自动重调时 API 失败: {e}"
                ),
                raw_output=raw_content,
                repair_attempted=True,
            ) from e

        json_obj, retry_error = _try_parse(raw_retry)
        duration_ms = int((time.time() - t0) * 1000)
        if json_obj is not None:
            logger.info("structured_chat JSON 自动重调成功")
            self._log_call(
                self.model,
                retry_temp,
                prompt_version,
                prompt,
                json.dumps(json_obj, ensure_ascii=False),
                duration_ms,
                True,
                prompt_tokens=token_pt,
                completion_tokens=token_ct,
                total_tokens=token_tt,
            )
            return json_obj

        error_msg = (
            f"模型输出 JSON 解析失败（原始+修复+重调均失败）: "
            f"first={first_error}; retry={retry_error}"
        )
        self._log_call(
            self.model,
            temperature,
            prompt_version,
            prompt,
            raw_retry or raw_content,
            duration_ms,
            False,
            error_msg,
            prompt_tokens=token_pt,
            completion_tokens=token_ct,
            total_tokens=token_tt,
        )
        raise AgentOutputParseError(
            message=(
                f"Agent 输出无法解析为合法 JSON。原始错误: {first_error}。"
                f"已尝试自动修复并重新调用模型，依然失败。请检查 prompt 和 schema_example 是否清晰明确。"
            ),
            raw_output=raw_retry or raw_content,
            repair_attempted=True,
        )

    @_with_retry
    def vision_structured_chat(
        self,
        prompt: str,
        image_base64: str,
        schema_example: Optional[Union[Dict[str, Any], str]] = None,
        temperature: float = 0.1,
        prompt_version: str = "vision",
        vl_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """多模态结构化输出（图表 critique 等）。"""
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")

        model = vl_model or get_effective_model()
        schema_text = json.dumps(schema_example, ensure_ascii=False, indent=2) if isinstance(schema_example, dict) else str(schema_example or "{}")
        system = (
            "你是科学图表质量评审助手。仅输出合法 JSON，不要 markdown。"
            f"\n\n输出格式示例：\n{schema_text}"
        )
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                ],
            },
        ]
        t0 = time.time()
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            timeout=self.timeout,
        )
        raw_content = response.choices[0].message.content or ""
        duration_ms = int((time.time() - t0) * 1000)
        try:
            parsed = _safe_json_loads(raw_content)
        except json.JSONDecodeError:
            parsed = _repair_json(raw_content)
        self._log_call(model, temperature, prompt_version, prompt[:200], json.dumps(parsed, ensure_ascii=False), duration_ms, True)
        return parsed

    # ==================== 多轮对话 ====================

    @_with_retry
    def chat_with_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> str:
        """多轮对话接口"""
        if not self.api_key:
            raise QwenError("QWEN_API_KEY not set")

        logger.debug(f"Calling Qwen chat_with_messages with {len(messages)} messages")
        t0 = time.time()

        try:
            logger.info(f"[LLM] chat_with_messages 开始调用 model={self.model} msgs={len(messages)}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 8192,
                timeout=self.timeout,
            )
            content = response.choices[0].message.content
            if content is None:
                raise QwenAPIError("Empty response from Qwen API")

            duration_ms = int((time.time() - t0) * 1000)
            self._log_call(self.model, temperature, "", str(messages), content, duration_ms, True)
            return content

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            self._log_call(self.model, temperature, "", str(messages), "", duration_ms, False, str(e))
            raise


# ==================== 全局单例 ====================

_qwen_client: Optional[QwenClient] = None
_qwen_client_fingerprint: Optional[str] = None


def _runtime_fingerprint() -> str:
    """运行时 LLM 配置指纹，用于检测模型/密钥切换后自动重建客户端。"""
    from app.core.llm_runtime import get_runtime_state

    key = get_effective_api_key()
    key_tail = key[-6:] if key else ""
    state = get_runtime_state()
    return "|".join([
        get_effective_base_url(),
        get_effective_model(),
        key_tail,
        "env" if state.use_env_api_key else "custom",
    ])


def get_qwen_client() -> QwenClient:
    """获取 Qwen 客户端单例（模型/密钥变更后自动重建）。"""
    global _qwen_client, _qwen_client_fingerprint
    fp = _runtime_fingerprint()
    if _qwen_client is None or _qwen_client_fingerprint != fp:
        _qwen_client = QwenClient()
        _qwen_client_fingerprint = fp
        logger.info("Qwen 客户端已按当前运行时配置重建 model=%s", _qwen_client.model)
    return _qwen_client


def _set_qwen_client(client: Optional[QwenClient]) -> None:
    """设置自定义 Qwen 客户端（用于 mock 注入）；传 None 则清除单例"""
    global _qwen_client
    _qwen_client = client


def reset_qwen_client() -> None:
    """清除单例，下次 get_qwen_client 按当前运行时配置重建"""
    global _qwen_client, _qwen_client_fingerprint
    _qwen_client = None
    _qwen_client_fingerprint = None


# ==================== 便捷函数 ====================

def qwen_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3
) -> str:
    """便捷的 Qwen 对话函数"""
    client = get_qwen_client()
    return client.chat(prompt=prompt, system_prompt=system_prompt, temperature=temperature)


def qwen_structured_chat(
    prompt: str,
    schema_example: Optional[Union[Dict[str, Any], str]] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    prompt_version: str = ""
) -> Dict[str, Any]:
    """
    便捷的 Qwen 结构化输出函数

    Args:
        prompt: 用户输入
        schema_example: JSON 格式示例
        system_prompt: 系统提示词
        temperature: 温度参数
        max_tokens: 最大生成 token 数
        prompt_version: Prompt 模板版本标识

    Returns:
        解析后的 JSON 字典

    Raises:
        AgentOutputParseError: JSON 解析失败
    """
    client = get_qwen_client()
    return client.structured_chat(
        prompt=prompt,
        schema_example=schema_example,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt_version=prompt_version
    )


def qwen_vision_structured_chat(
    prompt: str,
    image_base64: str,
    schema_example: Optional[Union[Dict[str, Any], str]] = None,
    prompt_version: str = "vision",
) -> Dict[str, Any]:
    """便捷 VLM 结构化输出（图表 critique）。"""
    client = get_qwen_client()
    return client.vision_structured_chat(
        prompt=prompt,
        image_base64=image_base64,
        schema_example=schema_example,
        prompt_version=prompt_version,
    )