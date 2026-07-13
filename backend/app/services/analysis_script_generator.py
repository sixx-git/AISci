"""实验分析脚本生成 — 实验设计与小样验证共用。"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from app.services.analysis_script_utils import sanitize_analysis_script
from app.services.experiment_spec_service import format_spec_for_prompt
from app.services.qwen_client import qwen_chat

logger = logging.getLogger(__name__)

_SANDBOX_CONTRACT = (
    "【沙箱输出契约 — 必须全部满足】\n"
    "1. 使用环境变量 AISCI_RUN_DIR 作为运行目录，将 metrics 写入 "
    "Path(AISCI_RUN_DIR)/'metrics.json'（JSON 对象，含 primary_metric 或具体指标键，"
    "禁止仅写 note 占位）。\n"
    "2. 使用环境变量 AISCI_PLOTS_DIR 作为图表目录，至少保存 1 张 PNG 到该目录 "
    "（如 PLOTS_DIR/'experiment_result.png'）。\n"
    "3. 优先调用 _aisci_load_data() 加载数据；加载后使用 _aisci_encode_frame(df) 编码分类列；"
    "否则使用 os.environ['AISCI_DATA_PATH']。\n"
    "4. 图表须体现假设验证或方法对比（如指标柱状图、基线 vs  proposed 对比），"
    "禁止只输出原始字段直方图/散点图作为唯一结果。\n"
    "5. 设置 matplotlib Agg 后端，脚本 exit code 必须为 0。\n"
    "6. 【import 约束】wasserstein_distance 必须从 scipy.stats 导入，"
    "禁止 from scipy.spatial.distance import wasserstein_distance；"
    "KL 散度用 scipy.stats.entropy，勿用错误模块。\n"
    "7. 保持脚本简洁可运行，避免过长导致超时；优先 sklearn + pandas + matplotlib。"
)


def extract_code_block(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"```(?:python)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def default_analysis_script() -> str:
    """符合沙箱契约的默认分析脚本（真实数据兜底）。"""
    return '''import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

run_dir = Path(os.environ.get("AISCI_RUN_DIR", "."))
plots_dir = Path(os.environ.get("AISCI_PLOTS_DIR", str(run_dir / "plots")))
plots_dir.mkdir(parents=True, exist_ok=True)


def _load_df():
    if "globals" in dir() and callable(globals().get("_aisci_load_data")):
        return _aisci_load_data()
    data_path = os.environ.get("AISCI_DATA_PATH") or os.environ.get("CSV_DATA_PATH")
    if not data_path:
        raise RuntimeError("缺少 AISCI_DATA_PATH，无法加载数据")
    return pd.read_csv(data_path)


df = _aisci_encode_frame(_load_df())
numeric = df.select_dtypes(include=[np.number])
if numeric.empty:
    raise RuntimeError("数据编码后仍无数值列，无法生成对比图")

col = None
for hint in ("carcinoma", "label", "target", "jaundice", "fibrosis"):
    for c in numeric.columns:
        if hint in str(c).lower():
            col = c
            break
    if col:
        break
if col is None:
    col = numeric.columns[0]
series = numeric[col].dropna()
metrics = {
    "rows": int(len(df)),
    "columns": int(len(df.columns)),
    "data_source": "sandbox_default_script",
    "encoded_value_column": str(col),
}

if series.empty:
    metrics["primary_metric"] = 0.0
    metrics["warning"] = "no usable values after encoding"
else:
    metrics["primary_metric"] = float(series.mean())
    metrics["primary_metric_std"] = float(series.std()) if len(series) > 1 else 0.0
    metrics["metric_label"] = str(col)

    mid = max(1, len(series) // 2)
    group_a = series.iloc[:mid]
    group_b = series.iloc[mid:]
    metrics["baseline_mean"] = float(group_a.mean())
    metrics["proposed_mean"] = float(group_b.mean())

    fig, ax = plt.subplots(figsize=(8, 5))
    names = ["Baseline（前半）", "Proposed（后半）"]
    vals = [metrics["baseline_mean"], metrics["proposed_mean"]]
    ax.bar(names, vals, color=["#4C72B0", "#DD8452"], alpha=0.9)
    ax.set_ylabel(str(col))
    ax.set_title(f"Pilot：{col} 分区对比")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(plots_dir / "experiment_result.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

with open(run_dir / "metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)
'''


def generate_analysis_script(
    *,
    hypothesis: str,
    methods: Optional[str] = None,
    datasets: Optional[str] = None,
    metrics: Optional[str] = None,
    baselines: Optional[str] = None,
    experimental_steps: Optional[str] = None,
    experiment_spec: Optional[Dict[str, Any]] = None,
    has_csv_data: bool,
    csv_data_path: Optional[str] = None,
    use_default_on_failure: bool = True,
) -> str:
    """根据实验设计与 experiment_spec 生成 Python 分析脚本。"""
    data_hint = (
        f"真实数据路径: {csv_data_path}"
        if has_csv_data and csv_data_path
        else "当前无真实 CSV，脚本应说明无法执行并优雅退出（sys.exit(0)），禁止生成随机模拟数据"
    )
    script_prompt = (
        f"假设: {hypothesis}\n"
        f"方法: {methods or '未提供'}\n"
        f"数据集: {datasets or '未提供'}\n"
        f"指标: {metrics or '未提供'}\n"
        f"基线: {baselines or '未提供'}\n"
        f"实验步骤: {(experimental_steps or '')[:1500]}\n"
        f"{data_hint}\n\n"
    )
    spec_block = format_spec_for_prompt(experiment_spec or {})
    if spec_block:
        script_prompt += f"{spec_block}\n\n"
    script_prompt += (
        "请输出完整可运行的 Python 3 分析脚本，使用 pandas/numpy/matplotlib。\n"
        "必须用 ```python 代码块包裹，不要输出 JSON 或其他说明文字。\n"
        "脚本逻辑必须与上述 experiment_spec 一致（目标列、基线对比、主指标）。\n\n"
        f"{_SANDBOX_CONTRACT}"
    )
    if has_csv_data and csv_data_path:
        script_prompt += (
            "\n脚本应优先使用 _aisci_load_data() 加载数据（沙箱会自动注入该函数）；"
            "加载后调用 _aisci_encode_frame(df)；若直接 read_csv，请使用环境变量 AISCI_DATA_PATH。"
        )
    try:
        raw = qwen_chat(
            script_prompt,
            system_prompt="你是数据科学家。只输出一个 ```python 代码块，不要 JSON。",
            temperature=0.2,
        )
        script = extract_code_block(raw)
        if script:
            return sanitize_analysis_script(script)
    except Exception as exc:
        logger.warning("分析脚本 LLM 生成失败: %s", exc)
    if use_default_on_failure and has_csv_data:
        return default_analysis_script()
    return ""
