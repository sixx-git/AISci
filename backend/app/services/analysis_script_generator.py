"""实验分析脚本生成 — 实验设计与小样验证共用。"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from app.services.analysis_script_utils import sanitize_analysis_script
from app.services.experiment_spec_service import format_spec_for_prompt, normalize_experiment_spec
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


def default_analysis_script(experiment_spec: Optional[Dict[str, Any]] = None) -> str:
    """符合沙箱契约的 spec 对齐验证脚本；无 spec 时返回空（禁止代理兜底）。"""
    if experiment_spec:
        return build_spec_validation_script(experiment_spec)
    return ""


def build_spec_validation_script(experiment_spec: Dict[str, Any]) -> str:
    """按 experiment_spec 生成确定性小样验证脚本：目标列 + 基线 vs proposed + 主指标。"""
    spec = normalize_experiment_spec(experiment_spec)
    embedded = json.dumps(
        {
            "target_column": spec.get("target_column"),
            "feature_columns": spec.get("feature_columns") or [],
            "baselines": (spec.get("baselines") or ["Baseline（对照）", "Proposed（本文方法）"])[:2],
            "primary_metric": spec.get("primary_metric") or "accuracy",
            "task_type": spec.get("task_type") or "classification",
            "split_strategy": spec.get("split_strategy") or "train_test",
        },
        ensure_ascii=False,
    )
    body = _SPEC_VALIDATION_SCRIPT_TEMPLATE.replace(
        "__SPEC_JSON_LITERAL__", repr(embedded)
    )
    return sanitize_analysis_script(body)


_SPEC_VALIDATION_SCRIPT_TEMPLATE = '''import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_squared_error,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

SPEC = json.loads(__SPEC_JSON_LITERAL__)
run_dir = Path(os.environ.get("AISCI_RUN_DIR", "."))
plots_dir = Path(os.environ.get("AISCI_PLOTS_DIR", str(run_dir / "plots")))
plots_dir.mkdir(parents=True, exist_ok=True)


def _resolve_target(df, spec_target):
    if spec_target and spec_target in df.columns:
        return spec_target
    hints = ("carcinoma", "label", "target", "outcome", "class", "jaundice")
    for hint in hints:
        for col in df.columns:
            if hint in str(col).lower():
                return col
    numeric = df.select_dtypes(include=[np.number]).columns
    return str(numeric[-1]) if len(numeric) else None


def _resolve_features(df, target, spec_features):
    cols = [c for c in (spec_features or []) if c in df.columns and c != target]
    if cols:
        return cols
    numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c != target]
    if numeric:
        return list(numeric)
    return [c for c in df.columns if c != target]


def _metric_score(y_true, y_pred, y_prob, metric_name, task_type):
    m = (metric_name or "accuracy").lower()
    if task_type == "regression" or m in ("rmse", "mse", "mae"):
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
    if m in ("f1", "f1_score"):
        avg = "binary" if len(np.unique(y_true)) <= 2 else "macro"
        return float(f1_score(y_true, y_pred, average=avg, zero_division=0))
    if m == "auc" and y_prob is not None and len(np.unique(y_true)) == 2:
        return float(roc_auc_score(y_true, y_prob))
    return float(accuracy_score(y_true, y_pred))


df = _aisci_encode_frame(_aisci_load_data())
target = _resolve_target(df, SPEC.get("target_column"))
if not target or target not in df.columns:
    raise RuntimeError("无法解析目标列: " + str(SPEC.get("target_column")))

features = _resolve_features(df, target, SPEC.get("feature_columns"))
if not features:
    raise RuntimeError("无可用特征列，无法完成假设验证")

work = df[features + [target]].dropna()
if len(work) < 8:
    raise RuntimeError("有效样本过少 (n=" + str(len(work)) + ")，无法完成小样验证")

X = work[features]
y_raw = work[target]
task_type = SPEC.get("task_type") or "classification"
if task_type != "regression":
    if pd.api.types.is_numeric_dtype(y_raw):
        y = y_raw.astype(int)
    else:
        y = pd.factorize(y_raw)[0]
    stratify = y if len(np.unique(y)) > 1 and len(np.unique(y)) < len(y) else None
    split_strategy = (SPEC.get("split_strategy") or "train_test").lower()
    if split_strategy == "row_half":
        mid = max(4, len(work) // 2)
        X_train, X_test = X.iloc[:mid], X.iloc[mid:]
        y_train, y_test = y[:mid], y[mid:]
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=stratify
        )
    baseline_model = LogisticRegression(max_iter=800)
    proposed_model = LogisticRegression(max_iter=800, class_weight="balanced")
    baseline_model.fit(X_train, y_train)
    proposed_model.fit(X_train, y_train)
    y_pred_b = baseline_model.predict(X_test)
    y_pred_p = proposed_model.predict(X_test)
    prob_b = (
        baseline_model.predict_proba(X_test)[:, 1]
        if hasattr(baseline_model, "predict_proba") and len(np.unique(y)) == 2
        else None
    )
    prob_p = (
        proposed_model.predict_proba(X_test)[:, 1]
        if hasattr(proposed_model, "predict_proba") and len(np.unique(y)) == 2
        else None
    )
else:
    y = pd.to_numeric(y_raw, errors="coerce")
    work = work.loc[y.notna()]
    X = work[features]
    y = y.loc[work.index]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    baseline_model = DummyRegressor(strategy="mean")
    proposed_model = Ridge(alpha=1.0)
    baseline_model.fit(X_train, y_train)
    proposed_model.fit(X_train, y_train)
    y_pred_b = baseline_model.predict(X_test)
    y_pred_p = proposed_model.predict(X_test)
    prob_b = prob_p = None

metric_name = SPEC.get("primary_metric") or "accuracy"
baseline_score = _metric_score(y_test, y_pred_b, prob_b, metric_name, task_type)
proposed_score = _metric_score(y_test, y_pred_p, prob_p, metric_name, task_type)
baseline_name, proposed_name = (SPEC.get("baselines") or ["Baseline", "Proposed"])[:2]

metrics = {
    "validation_mode": "spec_aligned",
    "data_source": "spec_validation_script",
    "target_column": target,
    "feature_count": len(features),
    "n_samples": int(len(work)),
    "task_type": task_type,
    "primary_metric": proposed_score,
    "primary_metric_name": metric_name,
    "baseline_score": baseline_score,
    "proposed_score": proposed_score,
    "baseline_name": baseline_name,
    "proposed_name": proposed_name,
    metric_name: proposed_score,
    "baseline_" + str(metric_name): baseline_score,
    "proposed_" + str(metric_name): proposed_score,
    "improvement": float(proposed_score - baseline_score),
}

fig, ax = plt.subplots(figsize=(8, 5))
names = [baseline_name, proposed_name]
vals = [baseline_score, proposed_score]
ax.bar(names, vals, color=["#4C72B0", "#DD8452"], alpha=0.9)
ax.set_ylabel(str(metric_name).upper())
ax.set_title("小样验证: " + str(baseline_name) + " vs " + str(proposed_name) + " (" + str(metric_name) + ")")
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
    if use_default_on_failure and has_csv_data and experiment_spec:
        return build_spec_validation_script(experiment_spec)
    return ""
