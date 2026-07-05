"""在同步/异步代码间安全调度阻塞任务。"""
from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Callable, Coroutine, TypeVar

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


async def run_blocking(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在独立线程中运行阻塞函数，避免卡住 FastAPI event loop。"""
    return await asyncio.to_thread(func, *args, **kwargs)
