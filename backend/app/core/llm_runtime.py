"""LLM 运行时配置（内存覆盖 .env，供 API 管理面板切换密钥/模型）"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.core.config import get_settings

settings = get_settings()

AVAILABLE_TEXT_MODELS: List[str] = [
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
    "qwen-long",
    "qwen2.5-72b-instruct",
    "qwen2.5-32b-instruct",
    "qwen2.5-14b-instruct",
    "qwen2.5-7b-instruct",
]

AVAILABLE_VL_MODELS: List[str] = [
    "qwen-vl-max",
    "qwen-vl-plus",
    "qwen2.5-vl-72b-instruct",
    "qwen2.5-vl-32b-instruct",
]


@dataclass
class LlmRuntimeState:
    use_env_api_key: bool = True
    api_key_override: Optional[str] = None
    model_override: Optional[str] = None
    vl_model_override: Optional[str] = None
    base_url_override: Optional[str] = None
    use_mock_llm_override: Optional[bool] = None


_state = LlmRuntimeState()


def mask_api_key(key: str) -> str:
    if not key or not key.strip():
        return ""
    trimmed = key.strip()
    if len(trimmed) <= 8:
        return "****"
    return f"{trimmed[:4]}****{trimmed[-4:]}"


def get_effective_api_key() -> str:
    if _state.use_env_api_key or not (_state.api_key_override or "").strip():
        return settings.QWEN_API_KEY
    return _state.api_key_override.strip()


def get_effective_base_url() -> str:
    override = (_state.base_url_override or "").strip()
    return override or settings.QWEN_BASE_URL


def get_effective_model() -> str:
    override = (_state.model_override or "").strip()
    return override or settings.QWEN_MODEL


def get_effective_vl_model() -> str:
    override = (_state.vl_model_override or "").strip()
    return override or settings.QWEN_VL_MODEL


def get_effective_use_mock_llm() -> bool:
    if _state.use_mock_llm_override is not None:
        return _state.use_mock_llm_override
    return settings.USE_MOCK_LLM


def get_runtime_state() -> LlmRuntimeState:
    return _state


def update_runtime(
    *,
    use_env_api_key: Optional[bool] = None,
    api_key: Optional[str] = None,
    clear_api_key_override: bool = False,
    model: Optional[str] = None,
    vl_model: Optional[str] = None,
    base_url: Optional[str] = None,
    use_mock_llm: Optional[bool] = None,
) -> LlmRuntimeState:
    if use_env_api_key is not None:
        _state.use_env_api_key = use_env_api_key
    if clear_api_key_override:
        _state.api_key_override = None
    elif api_key is not None:
        stripped = api_key.strip()
        _state.api_key_override = stripped or None
    if model is not None:
        _state.model_override = model.strip() or None
    if vl_model is not None:
        _state.vl_model_override = vl_model.strip() or None
    if base_url is not None:
        _state.base_url_override = base_url.strip() or None
    if use_mock_llm is not None:
        _state.use_mock_llm_override = use_mock_llm
    return _state


def build_config_snapshot() -> dict:
    effective_key = get_effective_api_key()
    env_key_configured = bool(settings.QWEN_API_KEY and settings.QWEN_API_KEY.strip())
    custom_key_configured = bool(
        not _state.use_env_api_key and (_state.api_key_override or "").strip()
    )
    return {
        "use_env_api_key": _state.use_env_api_key,
        "api_key_source": "env" if _state.use_env_api_key else "custom",
        "env_api_key_configured": env_key_configured,
        "custom_api_key_configured": custom_key_configured,
        "api_key_configured": bool(effective_key and effective_key.strip()),
        "api_key_masked": mask_api_key(effective_key),
        "model": get_effective_model(),
        "vl_model": get_effective_vl_model(),
        "base_url": get_effective_base_url(),
        "use_mock_llm": get_effective_use_mock_llm(),
        "env_model": settings.QWEN_MODEL,
        "env_vl_model": settings.QWEN_VL_MODEL,
        "env_base_url": settings.QWEN_BASE_URL,
        "available_models": AVAILABLE_TEXT_MODELS,
        "available_vl_models": AVAILABLE_VL_MODELS,
        "model_override": _state.model_override,
        "vl_model_override": _state.vl_model_override,
    }
