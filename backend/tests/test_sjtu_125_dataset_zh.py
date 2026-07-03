"""SJTU 125 Questions 中文数据集测试"""
from pathlib import Path

import json
import re

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "output" / "sjtu-125-questions" / "zh" / "questions.json"


def test_zh_dataset_exists_and_has_125_items():
    assert DATA.exists(), "请先运行 backend/scripts/build_sjtu_125_dataset_zh.py"
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    assert len(rows) == 125
    assert rows[0]["id"] == "sjtu_q_001"
    assert rows[0]["category"] == "数学科学"
    assert rows[0]["category_en"] == "Mathematical Sciences"
    assert rows[0]["research_question_en"]
    assert rows[0]["research_question"].endswith("？")


def test_zh_questions_contain_chinese():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    primes = [r for r in rows if "素数" in r["research_question"]]
    assert primes and primes[0]["category"] == "数学科学"
    for row in rows:
        assert len(re.findall(r"[\u4e00-\u9fff]", row["research_question"])) >= 3
