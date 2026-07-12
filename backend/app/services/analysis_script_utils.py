"""沙箱分析脚本的 import 修正与轻量清洗。"""
from __future__ import annotations

import re


def sanitize_analysis_script(script: str) -> str:
    """修正 LLM 脚本中常见的 import/API 错误，避免沙箱在 import 阶段崩溃。"""
    if not script:
        return script
    text = script
    replacements = [
        (
            "from scipy.spatial.distance import wasserstein_distance",
            "from scipy.stats import wasserstein_distance",
        ),
    ]
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
    text = re.sub(
        r"scipy\.spatial\.distance\.wasserstein_distance",
        "scipy.stats.wasserstein_distance",
        text,
    )
    if "matplotlib.use" not in text and "matplotlib" in text:
        text = "import matplotlib\nmatplotlib.use('Agg')\n" + text
    return text
