"""OCR 工具单元测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.rubric_observability import (
    enrich_item_observability,
    extract_elements_from_question,
    is_naked_explain_define,
    item_passes_observability,
    score_from_checklist,
)


class TestOCR(unittest.TestCase):
    def test_naked_explain(self):
        self.assertTrue(is_naked_explain_define("Does the report explain the mechanism?", []))
        self.assertFalse(
            is_naked_explain_define(
                "Does the report explain Non-IID data, i.e., that distributions differ across clients?",
                [],
            )
        )

    def test_extract_ie_clause(self):
        q = "Does the report explain X, i.e., that Y happens?"
        elems = extract_elements_from_question(q)
        self.assertTrue(elems)

    def test_checklist_score(self):
        self.assertEqual(score_from_checklist(3, 4, 3, 2), 4.0)
        self.assertEqual(score_from_checklist(2, 4, 3, 2), 2.0)
        self.assertEqual(score_from_checklist(1, 4, 3, 2), 0.0)

    def test_enrich_checklist(self):
        item = enrich_item_observability(
            {
                "question": "Does the report state A and B?",
                "required_elements": ["A", "B", "C"],
            },
            "information_acquisition",
        )
        self.assertEqual(item["judgment_mode"], "checklist")
        self.assertTrue(item_passes_observability(item, "information_acquisition"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
