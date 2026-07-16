"""composite_scorer 字段解析兼容测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.composite_scorer import (  # noqa: E402
    calculate_composite_rating,
    resolve_display_composite_score,
    resolve_impact_score,
)


class TestResolveComposite(unittest.TestCase):
    def test_new_format_prefers_composite(self):
        rating = {"composite_score": 87.0, "total_max": 100, "score_scale": "percent"}
        self.assertEqual(resolve_display_composite_score(rating, 171.0), 87.0)

    def test_old_200_raw_via_composite(self):
        rating = {
            "composite_score": 41.09,
            "composite_score_raw": 82.19,
            "total_max": 200,
        }
        self.assertEqual(resolve_display_composite_score(rating, 82.19), 41.09)

    def test_fallback_normalize_total_score(self):
        rating = {"total_max": 200}
        self.assertEqual(resolve_display_composite_score(rating, 82.19), 41.09)

    def test_fallback_raw_field(self):
        rating = {"composite_score_raw": 171.34, "total_max": 200}
        self.assertEqual(resolve_display_composite_score(rating, None), 85.67)

    def test_impact_calibrated_total(self):
        impact = {"calibrated_total": {"score": 26, "max": 30}}
        score, mx = resolve_impact_score(impact, {})
        self.assertEqual(score, 26)
        self.assertEqual(mx, 30)

    def test_impact_legacy_total_score(self):
        impact = {"total_score": 22}
        score, mx = resolve_impact_score(impact, {})
        self.assertEqual(score, 22)
        self.assertEqual(mx, 30)

    def test_calculate_writes_total_max_100(self):
        r = calculate_composite_rating(
            content_details=[{"score_percentage": 80}],
            impact_score=24,
        )
        self.assertEqual(r["total_max"], 100)
        self.assertEqual(r["score_scale"], "percent")
        self.assertAlmostEqual(r["composite_score"], 80 * 0.5 + (24 / 30 * 100) * 0.5, places=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
