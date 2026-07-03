"""文献零结果终止工作流与检索限流配置测试。"""
import pytest

from app.core.pipeline_exceptions import LiteratureNotFoundError
from app.services.pipeline_service import PipelineService
from app.skills.literature.literature_discovery_pipeline import (
    DEFAULT_SOURCES,
    INTER_QUERY_DELAY_SEC,
    MAX_QUERIES,
)
from app.skills.literature.search_papers_skill import (
    ARXIV_MIN_INTERVAL_SEC,
    HTTP_RETRY_BASE_DELAY_SEC,
    HTTP_RETRY_MAX,
    SOURCE_INTERVAL_SEC,
)


class TestLiteratureValidation:
    def test_empty_literature_raises(self):
        with pytest.raises(LiteratureNotFoundError, match="未找到相关文献"):
            PipelineService._validate_literature_results({})

    def test_facts_present_passes(self):
        PipelineService._validate_literature_results({"facts": [{"fact_id": "f1", "content": "x"}]})

    def test_retrieved_papers_present_passes(self):
        PipelineService._validate_literature_results({"retrieved_papers": [{"title": "Paper A"}]})


class TestRateLimitConfig:
    def test_discovery_throttle_defaults(self):
        assert MAX_QUERIES <= 3
        assert INTER_QUERY_DELAY_SEC >= 3.0
        assert DEFAULT_SOURCES.index("arxiv") > DEFAULT_SOURCES.index("openalex")

    def test_search_retry_defaults(self):
        assert HTTP_RETRY_MAX >= 4
        assert HTTP_RETRY_BASE_DELAY_SEC >= 5.0
        assert ARXIV_MIN_INTERVAL_SEC >= 3.5
        assert SOURCE_INTERVAL_SEC >= 1.5
