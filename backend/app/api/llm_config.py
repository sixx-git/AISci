"""LLM 配置 API — 切换 API 密钥与模型"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.llm_runtime import (
    AVAILABLE_QWEN_MODELS,
    build_config_snapshot,
    update_runtime,
)
from app.schemas.common import ResponseModel, success_response
from app.services.qwen_client import QwenClient, reset_qwen_client

logger = logging.getLogger(__name__)

router = APIRouter()


class LlmConfigResponse(BaseModel):
    use_env_api_key: bool
    api_key_source: str
    env_api_key_configured: bool
    custom_api_key_configured: bool
    api_key_configured: bool
    api_key_masked: str
    model: str
    base_url: str
    use_mock_llm: bool
    env_model: str
    env_base_url: str
    available_models: List[str]
    model_override: Optional[str] = None


class LlmConfigUpdateRequest(BaseModel):
    use_env_api_key: Optional[bool] = Field(None, description="True=使用 .env 密钥")
    api_key: Optional[str] = Field(None, description="自定义 API Key")
    clear_custom_api_key: bool = Field(False, description="清除已保存的自定义密钥")
    model: Optional[str] = Field(None, description="Qwen 模型（文本/多模态统一）")
    base_url: Optional[str] = Field(None, description="API Base URL")
    use_mock_llm: Optional[bool] = Field(None, description="Mock LLM 模式")


class LlmTestResponse(BaseModel):
    ok: bool
    model: str
    message: str
    latency_ms: Optional[int] = None


def _apply_client_singleton(use_mock: bool) -> None:
    reset_qwen_client()
    if use_mock:
        from app.services.mock_qwen_client import use_mock
        use_mock()
    else:
        try:
            from app.services.mock_qwen_client import restore_real_client
            restore_real_client()
        except Exception:
            reset_qwen_client()


@router.get("/config", response_model=ResponseModel[LlmConfigResponse])
def get_llm_config():
    """获取当前 LLM 配置（密钥脱敏）"""
    snap = build_config_snapshot()
    return success_response(data=LlmConfigResponse(**snap), message="获取 LLM 配置成功")


@router.put("/config", response_model=ResponseModel[LlmConfigResponse])
def update_llm_config(body: LlmConfigUpdateRequest):
    """更新运行时 LLM 配置（内存生效，重启后恢复 .env）"""
    if body.model and body.model not in AVAILABLE_QWEN_MODELS:
        logger.info("使用自定义 Qwen 模型: %s", body.model)

    update_runtime(
        use_env_api_key=body.use_env_api_key,
        api_key=body.api_key,
        clear_api_key_override=body.clear_custom_api_key,
        model=body.model,
        base_url=body.base_url,
        use_mock_llm=body.use_mock_llm,
    )

    from app.core.llm_runtime import get_effective_use_mock_llm
    _apply_client_singleton(get_effective_use_mock_llm())

    snap = build_config_snapshot()
    return success_response(data=LlmConfigResponse(**snap), message="LLM 配置已更新")


@router.post("/test", response_model=ResponseModel[LlmTestResponse])
def test_llm_connection():
    """测试当前配置能否用所选模型成功调用千问 API。"""
    from app.core.llm_runtime import get_effective_use_mock_llm, get_effective_model

    if get_effective_use_mock_llm():
        return success_response(
            data=LlmTestResponse(ok=True, model="mock-model", message="Mock 模式已启用，无需真实 API"),
            message="连接测试完成",
        )

    import time
    t0 = time.time()
    model = get_effective_model()
    try:
        reset_qwen_client()
        client = QwenClient()
        if not client.api_key:
            latency = int((time.time() - t0) * 1000)
            return success_response(
                data=LlmTestResponse(
                    ok=False,
                    model=model,
                    message="API Key 未配置",
                    latency_ms=latency,
                ),
                message="连接测试完成",
            )
        content = client.chat("请只回复 OK", temperature=0, max_tokens=8)
        latency = int((time.time() - t0) * 1000)
        preview = (content or "").strip()[:40]
        return success_response(
            data=LlmTestResponse(
                ok=True,
                model=model,
                message=f"模型 {model} 调用成功：{preview or 'OK'}",
                latency_ms=latency,
            ),
            message="连接测试完成",
        )
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        return success_response(
            data=LlmTestResponse(
                ok=False,
                model=model,
                message=str(e)[:500],
                latency_ms=latency,
            ),
            message="连接测试完成",
        )
