"""LLM 配置 API — 切换 API 密钥与模型"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.llm_runtime import (
    AVAILABLE_TEXT_MODELS,
    AVAILABLE_VL_MODELS,
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
    vl_model: str
    base_url: str
    use_mock_llm: bool
    env_model: str
    env_vl_model: str
    env_base_url: str
    available_models: List[str]
    available_vl_models: List[str]
    model_override: Optional[str] = None
    vl_model_override: Optional[str] = None


class LlmConfigUpdateRequest(BaseModel):
    use_env_api_key: Optional[bool] = Field(None, description="True=使用 .env 密钥")
    api_key: Optional[str] = Field(None, description="自定义 API Key（仅 use_env_api_key=false 时生效）")
    clear_custom_api_key: bool = Field(False, description="清除已保存的自定义密钥")
    model: Optional[str] = Field(None, description="文本模型")
    vl_model: Optional[str] = Field(None, description="视觉模型")
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
    if body.model and body.model not in AVAILABLE_TEXT_MODELS:
        # 允许自定义模型名，仅记录日志
        logger.info("使用自定义文本模型: %s", body.model)
    if body.vl_model and body.vl_model not in AVAILABLE_VL_MODELS:
        logger.info("使用自定义视觉模型: %s", body.vl_model)

    update_runtime(
        use_env_api_key=body.use_env_api_key,
        api_key=body.api_key,
        clear_api_key_override=body.clear_custom_api_key,
        model=body.model,
        vl_model=body.vl_model,
        base_url=body.base_url,
        use_mock_llm=body.use_mock_llm,
    )

    from app.core.llm_runtime import get_effective_use_mock_llm
    _apply_client_singleton(get_effective_use_mock_llm())

    snap = build_config_snapshot()
    return success_response(data=LlmConfigResponse(**snap), message="LLM 配置已更新")


@router.post("/test", response_model=ResponseModel[LlmTestResponse])
def test_llm_connection():
    """测试当前配置能否初始化 LLM 客户端"""
    from app.core.llm_runtime import get_effective_use_mock_llm, get_effective_model

    if get_effective_use_mock_llm():
        return success_response(
            data=LlmTestResponse(ok=True, model="mock-model", message="Mock 模式已启用，无需真实 API"),
            message="连接测试完成",
        )

    import time
    t0 = time.time()
    try:
        client = QwenClient()
        ok = bool(client.api_key and client.client)
        latency = int((time.time() - t0) * 1000)
        if not ok:
            return success_response(
                data=LlmTestResponse(
                    ok=False,
                    model=client.model,
                    message="API Key 未配置或客户端初始化失败",
                    latency_ms=latency,
                ),
                message="连接测试完成",
            )
        return success_response(
            data=LlmTestResponse(
                ok=True,
                model=client.model,
                message="客户端初始化成功",
                latency_ms=latency,
            ),
            message="连接测试完成",
        )
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        return success_response(
            data=LlmTestResponse(
                ok=False,
                model=get_effective_model(),
                message=str(e)[:300],
                latency_ms=latency,
            ),
            message="连接测试完成",
        )
