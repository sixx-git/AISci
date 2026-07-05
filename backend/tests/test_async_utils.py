"""async_utils 单元测试。"""
import asyncio
import unittest

from app.core.async_utils import run_coroutine_sync


class TestAsyncUtils(unittest.TestCase):
    async def _sample(self, value: int) -> int:
        return value + 1

    def test_run_coroutine_sync_without_loop(self):
        self.assertEqual(run_coroutine_sync(self._sample(1)), 2)

    def test_run_coroutine_sync_inside_running_loop(self):
        async def _runner() -> int:
            return run_coroutine_sync(self._sample(5))

        self.assertEqual(asyncio.run(_runner()), 6)


if __name__ == "__main__":
    unittest.main()
