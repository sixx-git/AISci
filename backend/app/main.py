"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import create_tables
from app.api import v1_router
from app.schemas.common import success_response

settings = get_settings()

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    description="基于 Qwen 大模型的 AI Scientist 系统",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(v1_router, prefix="/api/v1")


# ============= 基础接口 =============

@app.get("/", tags=["基础"])
async def root():
    """根路径"""
    return success_response(
        data={
            "name": settings.APP_NAME,
            "version": settings.VERSION
        },
        message="欢迎使用 AI Scientist API"
    )


@app.get("/health", tags=["基础"])
async def health_check():
    """健康检查接口"""
    return success_response(
        data={
            "status": "healthy",
            "version": settings.VERSION
        },
        message="服务运行正常"
    )


@app.get("/health/llm", tags=["基础"])
async def health_llm():
    """LLM 客户端健康检查 —— 不发起真实 API 调用"""
    api_key_configured = bool(settings.QWEN_API_KEY and settings.QWEN_API_KEY.strip())
    base_url_configured = bool(settings.QWEN_BASE_URL and settings.QWEN_BASE_URL.strip())

    client_init_ok = False
    init_error = None
    model = settings.QWEN_MODEL

    if settings.USE_MOCK_LLM:
        client_init_ok = True
        model = "mock-model"
    elif api_key_configured and base_url_configured:
        try:
            from app.services.qwen_client import QwenClient
            client = QwenClient()
            client_init_ok = bool(client.client)
            model = client.model
        except Exception as e:
            init_error = f"{type(e).__name__}: {str(e)[:200]}"

    return success_response(
        data={
            "use_mock_llm": settings.USE_MOCK_LLM,
            "qwen_api_key_configured": api_key_configured,
            "base_url_configured": base_url_configured,
            "model": model,
            "client_init_ok": client_init_ok,
            "error": init_error,
        },
        message="LLM health check completed"
    )


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print(f"{'='*60}")
    print(f"   {settings.APP_NAME} v{settings.VERSION} 启动中...")
    print(f"{'='*60}")
    print()
    
    # 初始化数据库
    print("[1/3] 初始化数据库...")
    create_tables()
    print("    数据库表创建成功")
    print()
    
    # LLM 客户端初始化
    print("[2/3] 初始化 LLM 客户端...")
    if settings.USE_MOCK_LLM:
        from app.services.mock_qwen_client import use_mock
        use_mock()
        print("    ⚠ Mock LLM 模式已启用（model: mock-model）")
        print("    ⚠ 不会发起真实 API 调用，所有 LLM 输出为模拟数据")
        print("    ⚠ 此模式仅用于开发调试，不可用于生产环境")
    elif not settings.QWEN_API_KEY:
        print("    ⚠ QWEN_API_KEY 未设置")
        print("    ⚠ Pipeline 运行时会因缺少 API Key 而失败")
        print("    ⚠ 如需在无 API Key 时跑通 Pipeline，请在 .env 中设置 USE_MOCK_LLM=true")
    else:
        print(f"    ✓ 千问模型: {settings.QWEN_MODEL}")
        print(f"    ✓ API 地址: {settings.QWEN_BASE_URL}")
        print(f"    ✓ API Key: 已配置 ({len(settings.QWEN_API_KEY)} 字符)")
    print()
    
    print(f"[3/3] 启动完成！")
    print()
    print(f"📚 API 文档: http://localhost:{settings.BACKEND_PORT}/docs")
    print(f"🔧 服务地址: http://localhost:{settings.BACKEND_PORT}")
    print()
    print(f"{'='*60}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print()
    print(f"{'='*60}")
    print(f"   {settings.APP_NAME} 正在关闭...")
    print(f"{'='*60}")


# ============= 全局异常处理 =============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": str(exc) if settings.DEBUG else None,
            "timestamp": None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
