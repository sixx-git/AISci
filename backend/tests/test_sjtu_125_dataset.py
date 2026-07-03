"""SJTU 125 Questions 数据集构建测试"""
from pathlib import Path

import json

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "output" / "sjtu-125-questions" / "en" / "questions.json"


def test_dataset_exists_and_has_125_items():
    assert DATA.exists(), "请先运行 backend/scripts/build_sjtu_125_dataset.py"
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    assert len(rows) == 125
    assert rows[0]["id"] == "sjtu_q_001"
    assert "research_question" in rows[0]
    assert "file_description" in rows[0]
    assert "context" in rows[0]


def test_math_questions_categorized():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    primes = [r for r in rows if "prime numbers" in r["research_question"].lower()]
    assert primes and primes[0]["category"] == "Mathematical Sciences"
