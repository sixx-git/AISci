"""
FastAPI 应用入口
"""
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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

# 配置 CORS（CORS_ORIGINS=* 时允许任意来源）
_cors_origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_origins == ["*"] else _cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(v1_router, prefix="/api/v1")

# 静态资源：/storage/* -> backend/storage/*
_storage_root = Path(__file__).resolve().parent.parent / "storage"
_storage_root.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(_storage_root)), name="storage")

# 生产镜像：托管 frontend/dist（与 API 同端口）
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_spa_index = _frontend_dist / "index.html"


# ============= 基础接口 =============

@app.get("/", tags=["基础"])
async def root():
    """根路径：有前端构建产物时返回 SPA，否则返回 API 欢迎信息"""
    if _spa_index.is_file():
        return FileResponse(_spa_index)
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
    from app.services.cloud_db import database_backend_label

    return success_response(
        data={
            "status": "healthy",
            "version": settings.VERSION,
            "database": database_backend_label(settings.DATABASE_URL),
        },
        message="服务运行正常"
    )


@app.get("/health/llm", tags=["基础"])
async def health_llm():
    """LLM 客户端健康检查 —— 不发起真实 API 调用"""
    from app.core.llm_runtime import (
        build_config_snapshot,
        get_effective_use_mock_llm,
    )

    snap = build_config_snapshot()
    api_key_configured = snap["api_key_configured"]
    base_url_configured = bool(snap["base_url"] and str(snap["base_url"]).strip())
    use_mock = get_effective_use_mock_llm()

    client_init_ok = False
    init_error = None
    model = snap["model"]

    if use_mock:
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
            "use_mock_llm": use_mock,
            "qwen_api_key_configured": api_key_configured,
            "api_key_source": snap["api_key_source"],
            "api_key_masked": snap["api_key_masked"],
            "base_url_configured": base_url_configured,
            "base_url": snap["base_url"],
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
    
    # 初始化数据库（Meoo：SQLite 先从 Supabase Storage 恢复）
    print("[1/3] 初始化数据库...")
    from app.services.cloud_db import (
        cloud_sqlite_sync_enabled,
        database_backend_label,
        download_iterative_experiments_bundle,
        download_pingfenbiao_jobs_bundle,
        download_reports_bundle,
        download_shaxiang_data_bundle,
        download_sqlite,
        scrub_demo_report_references,
        scrub_stuck_report_quality_hints,
        start_periodic_sync,
    )

    restored = download_sqlite(settings.DATABASE_URL)
    if restored:
        print("    已从 Meoo Supabase Storage 恢复数据库")
    try:
        scrubbed = scrub_demo_report_references(settings.DATABASE_URL)
        if scrubbed:
            print(f"    已清理报告占位引用 {scrubbed} 条")
    except Exception as exc:
        print(f"    [WARN] 报告引用清理跳过: {exc}")
    try:
        hint_scrubbed = scrub_stuck_report_quality_hints(settings.DATABASE_URL)
        if hint_scrubbed:
            print(f"    已清理卡住的报告质量提示 {hint_scrubbed} 条")
    except Exception as exc:
        print(f"    [WARN] 报告质量提示清理跳过: {exc}")
    reports_ok = download_reports_bundle()
    if reports_ok:
        print("    已从 Meoo Supabase Storage 恢复报告文件")
    predict_ok = download_pingfenbiao_jobs_bundle()
    if predict_ok:
        print("    已从 Meoo Supabase Storage 恢复预测任务记录")
    ie_ok = download_iterative_experiments_bundle()
    if ie_ok:
        print("    已从 Meoo Supabase Storage 恢复迭代实验投影")
    sx_ok = download_shaxiang_data_bundle()
    if sx_ok:
        print("    已从 Meoo Supabase Storage 恢复 shaxiang 实验数据")
    create_tables()
    sync_interval = int(getattr(settings, "AISCI_CLOUD_DB_SYNC_INTERVAL_SEC", 10800) or 10800)
    start_periodic_sync(settings.DATABASE_URL, interval_sec=sync_interval)
    print(f"    数据库表创建成功 ({database_backend_label(settings.DATABASE_URL)})")
    if cloud_sqlite_sync_enabled(settings.DATABASE_URL):
        print(f"    SQLite→Storage 回写周期: {sync_interval}s ({sync_interval / 3600:.1f}h)")

    from app.core.database import SessionLocal
    from app.api.pipeline import fail_orphaned_pipeline_runs, set_server_boot_time
    from datetime import timezone, timedelta

    boot_time = datetime.now(timezone(timedelta(hours=8)))
    set_server_boot_time(boot_time)

    db = SessionLocal()
    try:
        n = fail_orphaned_pipeline_runs(db, boot_time=boot_time)
        if n:
            print(f"    已清理 {n} 个中断的 Pipeline 运行")
    finally:
        db.close()
    print()
    
    # LLM 客户端初始化
    print("[2/3] 初始化 LLM 客户端...")
    if settings.USE_MOCK_LLM:
        from app.services.mock_qwen_client import use_mock
        use_mock()
        print("    [WARN] Mock LLM 模式已启用（model: mock-model）")
        print("    [WARN] 不会发起真实 API 调用，所有 LLM 输出为模拟数据")
        print("    [WARN] 此模式仅用于开发调试，不可用于生产环境")
    elif not settings.QWEN_API_KEY:
        print("    [WARN] QWEN_API_KEY 未设置")
        print("    [WARN] Pipeline 运行时会因缺少 API Key 而失败")
        print("    [WARN] 如需在无 API Key 时跑通 Pipeline，请在 .env 中设置 USE_MOCK_LLM=true")
    else:
        from app.core.llm_runtime import get_effective_model
        eff = get_effective_model()
        print(f"    [OK] 千问模型: {eff}")
        if eff != settings.QWEN_MODEL:
            print(f"    [OK] .env 默认: {settings.QWEN_MODEL}（已被运行时覆盖）")
        print(f"    [OK] API 地址: {settings.QWEN_BASE_URL}")
        print(f"    [OK] API Key: 已配置 ({len(settings.QWEN_API_KEY)} 字符)")
    print()
    
    print(f"[3/3] 启动完成！")
    print()
    print(f"API 文档: http://localhost:{settings.BACKEND_PORT}/docs")
    print(f"服务地址: http://localhost:{settings.BACKEND_PORT}")
    print()
    print(f"{'='*60}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    from app.services.cloud_db import stop_periodic_sync

    stop_periodic_sync(settings.DATABASE_URL)
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


# SPA 回退：非 API / 非已挂载路径时返回 index.html（须放在路由末尾）
if _spa_index.is_file():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = _frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_spa_index)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
