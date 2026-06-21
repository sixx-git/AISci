"""arXiv 数据源测试"""
import asyncio
import unittest

from app.services.literature_sources.arxiv_source import ArxivSource


class TestArxivSource(unittest.TestCase):
    def test_direct_api_search(self):
        source = ArxivSource(timeout=20, max_retries=1)
        papers = source.search("cat:cs.LG AND federated", max_results=3)
        self.assertGreater(len(papers), 0)
        self.assertTrue(papers[0].title)

    def test_search_with_fallback_chain(self):
        source = ArxivSource(timeout=20, max_retries=1)
        papers, fallback, warning = source.search_with_fallback("federated learning", max_results=3)
        self.assertGreater(len(papers), 0)
        # 直连成功时不应 fallback；若网络受限则可能 OpenAlex/本地缓存
        if fallback:
            self.assertTrue(warning)

    def test_fallback_path_resolution(self):
        source = ArxivSource(fallback_data_path="./data/arxiv_fallback.json")
        path = source._resolve_fallback_path()
        self.assertTrue(path.endswith("arxiv_fallback.json"))


if __name__ == "__main__":
    unittest.main()
