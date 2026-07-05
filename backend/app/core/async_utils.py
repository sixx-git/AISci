"""在同步代码中安全运行协程（兼容 FastAPI 已有 event loop 的场景）。"""
from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_coroutine_sync(coro: Coroutine[Any, Any, T], *, timeout: float | None = None) -> T:
    """在同步上下文中执行协程；若当前线程已有 running loop，则在新线程中 asyncio.run。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if timeout is not None:
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        return asyncio.run(coro)

    def _runner() -> T:
        if timeout is not None:
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_runner).result()
