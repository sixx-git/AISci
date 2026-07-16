"""
将请求转发到本地 pingfenbiao Web 服务（默认 :8765）。

前端经 Vite 已有的 /api → :8000 代理访问本路由，避免依赖 /pingfenbiao 专用反代
（旧 Vite 进程常未加载该配置，导致「预测」页不可用）。
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pingfenbiao", tags=["pingfenbiao-proxy"])

_HOP_BY_HOP = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _base_url() -> str:
    return (
        os.environ.get("PINGFENBIAO_URL")
        or os.environ.get("PINGFENBIAO_BASE_URL")
        or "http://127.0.0.1:8765"
    ).rstrip("/")


@router.get("/health")
async def pingfenbiao_health():
    """探测下游 pingfenbiao 是否可达。"""
    base = _base_url()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # history 接口轻量且不依赖鉴权
            r = await client.get(f"{base}/api/impact/history")
        return {
            "ok": r.status_code < 500,
            "upstream": base,
            "status_code": r.status_code,
        }
    except Exception as exc:
        return {
            "ok": False,
            "upstream": base,
            "error": str(exc),
            "hint": "请启动 scripts/run_pingfenbiao.bat（uvicorn app:app --port 8765）",
        }


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_pingfenbiao(path: str, request: Request) -> Response:
    base = _base_url()
    target = f"{base}/{path.lstrip('/')}"
    if request.url.query:
        target = f"{target}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    body = await request.body()

    # 长任务（generate / score / impact）可能较久；上传也需较大超时
    timeout = httpx.Timeout(600.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            upstream = await client.request(
                method=request.method,
                url=target,
                content=body if body else None,
                headers=headers,
            )
    except httpx.ConnectError as exc:
        logger.warning("pingfenbiao 不可达: %s (%s)", target, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"无法连接预测服务 {base}。"
                "请先运行 scripts\\run_pingfenbiao.bat，"
                "或设置环境变量 PINGFENBIAO_URL。"
            ),
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"预测服务超时: {target}") from exc
    except Exception as exc:
        logger.exception("pingfenbiao 代理失败")
        raise HTTPException(status_code=502, detail=f"预测服务代理失败: {exc}") from exc

    excluded = {"content-encoding", "transfer-encoding", "content-length", "connection"}
    out_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in excluded
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get("content-type"),
    )
