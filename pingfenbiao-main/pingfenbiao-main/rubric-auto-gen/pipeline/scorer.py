"""
自动评分模块 — 共用实现见 common/scorer.py。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.scorer import (  # noqa: E402
    Scorer,
    normalize_score,
    prepare_report_text,
    PROMPT_SCORE_BATCH,
    PROMPT_SCORE_SINGLE,
)

__all__ = [
    "Scorer",
    "normalize_score",
    "prepare_report_text",
    "PROMPT_SCORE_BATCH",
    "PROMPT_SCORE_SINGLE",
]
