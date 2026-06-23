"""Phase 4 — Gap 闭环双阈值 / 多轮补搜 / 项目配置"""
import unittest

from app.services.data_finder_gap_search import (
    build_gap_search_queries,
    resolve_gap_thresholds,
    should_run_gap_enrichment,
)


class TestGapThresholds(unittest.TestCase):
    def test_resolve_from_project_and_options(self):
        thr = resolve_gap_thresholds(
            {"data_acquisition": {"coverage_gap_threshold": 65, "max_gap_rounds": 3}},
            {"data_spec_gap_threshold": 55},
        )
        self.assertEqual(thr["coverage_gap_threshold"], 65.0)
        self.assertEqual(thr["data_spec_gap_threshold"], 55.0)
        self.assertEqual(thr["max_gap_rounds"], 3)

    def test_should_run_when_data_spec_low(self):
        cov = {
            "completeness_score": 85,
            "data_spec_coverage": {
                "data_spec_score": 40,
                "entities_requested": ["patient_id"],
                "targets_requested": ["accuracy"],
            },
        }
        self.assertTrue(should_run_gap_enrichment(cov, threshold=70, data_spec_threshold=60))

    def test_should_skip_when_both_high(self):
        cov = {
            "completeness_score": 85,
            "data_spec_coverage": {
                "data_spec_score": 90,
                "entities_requested": ["id"],
            },
        }
        self.assertFalse(should_run_gap_enrichment(cov, threshold=70, data_spec_threshold=60))

    def test_gap_queries_include_spec_misses(self):
        queries = build_gap_search_queries(
            {"gaps": ["未命中外部开放数据库候选"]},
            None,
            {"dataset_keywords": ["protein"]},
            data_spec_coverage={
                "entities_miss": ["patient_id"],
                "targets_miss": ["f1_score"],
            },
        )
        self.assertTrue(any("patient_id" in q for q in queries))
        self.assertTrue(any("f1" in q.lower() for q in queries))


if __name__ == "__main__":
    unittest.main()
