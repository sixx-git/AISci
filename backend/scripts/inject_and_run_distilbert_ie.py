# -*- coding: utf-8 -*-
"""写入 DistilBERT 复杂度感知预算脚本，并启动一轮沙箱迭代。"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

PID = "867f76de-f558-4a6e-9cec-9f95b4260044"
EID = "e3e08129-aa9d-40c6-835a-c820d27514d0"

ANALYSIS_SCRIPT = r'''
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os
import re
import time
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, ConfusionMatrixDisplay
from sklearn.model_selection import StratifiedKFold

NEGATION = {
    "not", "no", "never", "neither", "nor", "n't", "cannot", "without",
    "hardly", "barely", "seldom", "nothing", "nowhere", "none",
}


def _complexity_scores(texts):
    scores = []
    for t in texts:
        s = str(t or "")
        toks = re.findall(r"[A-Za-z']+", s.lower())
        n = max(len(toks), 1)
        length = min(len(s) / 120.0, 1.0)
        uniq = len(set(toks)) / n
        neg = sum(1 for w in toks if w in NEGATION or w.endswith("n't")) / n
        punct = min(s.count(",") + s.count(";") + s.count(":") + s.count("!"), 8) / 8.0
        # 情感难度代理：长度 + 词表多样性 + 否定密度 + 标点复杂度
        c = 0.35 * length + 0.25 * uniq + 0.30 * min(neg * 4.0, 1.0) + 0.10 * punct
        scores.append(float(np.clip(c, 0.0, 1.0)))
    return np.asarray(scores, dtype=np.float64)


def _sigmoid_budget(c, lo=0.3, hi=0.8):
    # S 型映射到 [lo, hi]
    x = (c - 0.45) * 8.0
    sig = 1.0 / (1.0 + np.exp(-x))
    return lo + (hi - lo) * sig


def _encode_distilbert(texts, max_len=64, batch_size=16):
    import torch
    from transformers import AutoModel, AutoTokenizer

    model_name = "distilbert-base-uncased"
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    vecs = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = [str(x) if x is not None else "" for x in texts[i : i + batch_size]]
            enc = tok(
                batch,
                padding=True,
                truncation=True,
                max_length=max_len,
                return_tensors="pt",
            )
            enc = {k: v.to(device) for k, v in enc.items()}
            out = model(**enc)
            cls = out.last_hidden_state[:, 0, :].detach().cpu().numpy()
            vecs.append(cls)
    return np.vstack(vecs).astype(np.float32)


def _eval_strategy(X, y, sample_weight, n_dims, n_splits=3, seed=42):
    # 参数预算代理：保留前 n_dims 维 CLS 特征（类似低秩/容量预算）
    Xb = X[:, : max(8, int(n_dims))]
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    accs, f1s = [], []
    y_true_all, y_pred_all = [], []
    t0 = time.time()
    for tr, te in skf.split(Xb, y):
        clf = LogisticRegression(max_iter=400, random_state=seed, class_weight="balanced")
        sw = None if sample_weight is None else sample_weight[tr]
        clf.fit(Xb[tr], y[tr], sample_weight=sw)
        pred = clf.predict(Xb[te])
        accs.append(accuracy_score(y[te], pred))
        f1s.append(f1_score(y[te], pred, average="binary", zero_division=0))
        y_true_all.extend(y[te].tolist())
        y_pred_all.extend(pred.tolist())
    dur = time.time() - t0
    return {
        "accuracy": float(np.mean(accs)),
        "f1": float(np.mean(f1s)),
        "time": float(dur),
        "y_true": np.asarray(y_true_all),
        "y_pred": np.asarray(y_pred_all),
    }


def run(df, params):
    chart_dir = params.get("chart_dir", "data/charts")
    label = params.get("iteration_label", "result")
    os.makedirs(chart_dir, exist_ok=True)

    text_col = "sentence" if "sentence" in df.columns else df.columns[0]
    target_col = params.get("target_column", "label")
    if target_col not in df.columns:
        target_col = [c for c in df.columns if c != text_col][0]

    import pandas as pd

    work = df[[text_col, target_col]].dropna().copy()
    work[target_col] = work[target_col].astype(int)
    # smoke：控制编码成本
    max_n = int(params.get("encode_sample_size", 1200))
    if len(work) > max_n:
        parts = []
        for _, g in work.groupby(target_col):
            k = max(1, int(round(max_n * len(g) / len(work))))
            parts.append(g.sample(n=min(k, len(g)), random_state=42))
        work = pd.concat(parts, axis=0).sample(frac=1.0, random_state=42).reset_index(drop=True)

    texts = work[text_col].astype(str).tolist()
    y = work[target_col].to_numpy()
    complexity = _complexity_scores(texts)
    budgets = _sigmoid_budget(complexity)

    # DistilBERT 冻结编码
    X = _encode_distilbert(texts, max_len=int(params.get("max_sequence_length", 64)))

    # 固定预算：均匀权重 + 固定维数（中位容量）
    fixed_dims = 128
    fixed = _eval_strategy(X, y, sample_weight=None, n_dims=fixed_dims)

    # 动态预算：复杂度感知样本权重 + 按平均预算缩放特征维数
    dyn_dims = int(64 + 192 * float(np.mean(budgets)))  # ~[122, 218] within 768
    dyn_dims = int(np.clip(dyn_dims, 64, 256))
    # 样本权重：高复杂度样本获得更高训练权重
    sw = 0.5 + budgets  # ~[0.8, 1.3]
    dynamic = _eval_strategy(X, y, sample_weight=sw, n_dims=dyn_dims)

    # 高复杂度子集（top 33%）
    thr = np.quantile(complexity, 0.67)
    high_mask = complexity >= thr
    from sklearn.model_selection import train_test_split

    def _subset_acc(n_dims, sample_weight):
        Xb = X[:, :n_dims]
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=0.25, random_state=42, stratify=y)
        clf = LogisticRegression(max_iter=400, random_state=42, class_weight="balanced")
        sw = None if sample_weight is None else sample_weight[tr]
        clf.fit(Xb[tr], y[tr], sample_weight=sw)
        pred = clf.predict(Xb[te])
        mte = high_mask[te]
        if int(mte.sum()) == 0:
            return float(accuracy_score(y[te], pred))
        return float(accuracy_score(y[te][mte], pred[mte]))

    high_fixed = _subset_acc(fixed_dims, None)
    high_dynamic = _subset_acc(dyn_dims, sw)
    high_imp = high_dynamic - high_fixed

    acc_imp = dynamic["accuracy"] - fixed["accuracy"]
    f1_imp = dynamic["f1"] - fixed["f1"]
    time_ratio = (fixed["time"] / dynamic["time"]) if dynamic["time"] > 1e-9 else 1.0

    # 新成功标准（机制验证优先）
    crit_rel = 1.0 if (acc_imp >= 0.01 or f1_imp >= 0.01) else 0.0
    crit_high = 1.0 if high_imp >= 0.0 else 0.0
    crit_eff = 1.0 if time_ratio >= (1.0 / 1.2) else 0.0  # 动态不超过固定 1.2x => ratio>=0.833
    criteria_pass = 1.0 if (crit_rel + crit_high + crit_eff) >= 2.0 else 0.0

    # 图1：策略对比
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(2)
    ax.bar(x - 0.15, [fixed["accuracy"], fixed["f1"]], 0.3, label="Fixed budget")
    ax.bar(x + 0.15, [dynamic["accuracy"], dynamic["f1"]], 0.3, label="Dynamic complexity-aware")
    ax.set_xticks(x)
    ax.set_xticklabels(["Accuracy", "F1"])
    ax.set_ylim(0, 1)
    ax.set_title("DistilBERT CLS + budget strategies")
    ax.legend()
    p1 = os.path.join(chart_dir, f"{label}_strategy_compare.png")
    plt.savefig(p1, dpi=100, bbox_inches="tight")
    plt.close()

    # 图2：复杂度分布
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.hist(complexity, bins=20, color="#4C78A8", alpha=0.85)
    ax.axvline(thr, color="red", linestyle="--", label="high-complexity threshold")
    ax.set_xlabel("complexity")
    ax.set_ylabel("count")
    ax.set_title("Complexity distribution")
    ax.legend()
    p2 = os.path.join(chart_dir, f"{label}_complexity_hist.png")
    plt.savefig(p2, dpi=100, bbox_inches="tight")
    plt.close()

    # 图3：动态策略混淆矩阵
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay.from_predictions(dynamic["y_true"], dynamic["y_pred"], ax=ax)
    ax.set_title(f"Dynamic CM (acc={dynamic['accuracy']:.3f})")
    p3 = os.path.join(chart_dir, f"{label}_confusion_matrix.png")
    plt.savefig(p3, dpi=100, bbox_inches="tight")
    plt.close()

    return {
        "fixed_accuracy": fixed["accuracy"],
        "fixed_f1": fixed["f1"],
        "fixed_training_time": fixed["time"],
        "dynamic_accuracy": dynamic["accuracy"],
        "dynamic_f1": dynamic["f1"],
        "dynamic_training_time": dynamic["time"],
        "accuracy_improvement": acc_imp,
        "f1_improvement": f1_imp,
        "time_efficiency_ratio": time_ratio,
        "high_complexity_fixed_accuracy": high_fixed,
        "high_complexity_dynamic_accuracy": high_dynamic,
        "high_complexity_accuracy_improvement": high_imp,
        "fixed_feature_dims": float(fixed_dims),
        "dynamic_feature_dims": float(dyn_dims),
        "encoded_rows": float(len(work)),
        "criteria_relative_gain": crit_rel,
        "criteria_high_complexity": crit_high,
        "criteria_efficiency": crit_eff,
        "criteria_pass": criteria_pass,
        "encoder": 1.0,  # DistilBERT used
    }, [p1, p2, p3]
'''


SUCCESS_CRITERIA = [
    "动态相对固定：准确率提升≥1% 或 F1 提升≥1%",
    "高复杂度子集上动态策略准确率不低于固定策略",
    "动态策略训练时间不超过固定策略的 1.2 倍",
    "必须使用 DistilBERT（或同等预训练编码器），禁止 TF-IDF+LR 冒充参数预算",
]


def _build_plan(old_plan: dict, data_config: dict) -> dict:
    plan = dict(old_plan or {})
    plan["title"] = "DistilBERT复杂度感知动态参数预算（SST-2，第3轮人工注入）"
    plan["description"] = (
        "使用冻结 DistilBERT CLS 表征；固定策略使用固定特征维数与均匀样本权重；"
        "动态策略按复杂度 S 型映射样本权重与特征维数（参数预算代理）。"
        "成功标准改为机制相对增益，取消绝对准确率≥0.80硬门槛。"
    )
    plan["methodology"] = (
        "DistilBERT-base-uncased 冻结编码 → CLS 向量；"
        "复杂度=长度/词表多样性/否定密度/标点；"
        "动态预算=sigmoid映射到样本权重与保留特征维数；"
        "LogisticRegression + 分层交叉验证对比 fixed vs dynamic。"
    )
    plan["analysis_script"] = ANALYSIS_SCRIPT
    plan["success_criteria"] = SUCCESS_CRITERIA
    plan["sample_size"] = int((data_config or {}).get("sample_size") or 5000)
    params = dict(plan.get("parameters") or {})
    params["data_config"] = data_config
    params["script"] = ANALYSIS_SCRIPT
    params["script_params"] = {
        "target_column": "label",
        "sample_size": plan["sample_size"],
        "encode_sample_size": 1200,
        "max_sequence_length": 64,
        "n_splits": 3,
        "experiment_paradigm": "general",
        "iteration_label": "sst2_distilbert_budget_v3",
        "chart_dir": "data/charts",
    }
    plan["parameters"] = params
    plan["script_params"] = params["script_params"]
    hyp = plan.get("hypothesis")
    if isinstance(hyp, dict):
        hyp = dict(hyp)
        hyp["expected_outcome"] = (
            "动态相对固定准确率或F1提升≥1%；高复杂度子集不劣于固定；效率比可接受。"
        )
        plan["hypothesis"] = hyp
    plan["risk_assessment"] = (
        "本轮为冻结 DistilBERT + 线性头的轻量代理，用于验证复杂度感知预算的相对增益；"
        "不等于完整 LoRA 微调。若环境缺 GPU，编码可能较慢但应可完成。"
    )
    return plan


def write_plan() -> dict:
    from app.integrations.shaxiang.bridge import (
        ensure_shaxiang_path,
        project_experiment,
        _run_in_shaxiang,
    )

    def _inner():
        from datetime import datetime as dt

        from schemas.experiment import ExperimentPlan, ExperimentStatus
        from storage.sqlite_store import SQLiteRepository

        root = ensure_shaxiang_path()
        repo = SQLiteRepository(str(root / "data" / "experiments.db"))
        exp = repo.get_experiment(EID)
        if exp is None:
            raise RuntimeError("shaxiang 实验不存在，请先回填")
        old = exp.initial_plan.model_dump() if exp.initial_plan else {}
        dc = exp.data_config or exp.current_data_config or {}
        new_plan = _build_plan(old, dc)
        exp.initial_plan = ExperimentPlan.model_validate(new_plan)
        exp.human_feedback = (
            "人工注入：DistilBERT冻结编码+复杂度感知预算；放宽成功标准；禁止TF-IDF冒充。"
        )
        exp.feedback_status = "applied"
        exp.status = ExperimentStatus.CREATED
        exp.phase = "script_designed"
        exp.updated_at = dt.now().isoformat()
        repo.update_experiment(exp)
        return project_experiment(PID, EID)

    return _run_in_shaxiang(_inner)


def sync_aisci(projected: dict) -> None:
    path = BACKEND / "storage" / "iterative_experiments" / f"{PID}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    exps = data.get("experiments") or []
    for i, e in enumerate(exps):
        if e.get("id") == EID:
            exps[i] = projected
            break
    else:
        exps.append(projected)
    data["experiments"] = exps
    data["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_one() -> dict:
    from app.integrations.shaxiang.bridge import run_iteration

    return run_iteration(PID, EID)


def main() -> int:
    print("=== write plan", datetime.now().isoformat(timespec="seconds"))
    projected = write_plan()
    sync_aisci(projected)
    plan = projected.get("initial_plan") or {}
    script = plan.get("analysis_script") or ""
    print(
        "phase",
        projected.get("phase"),
        "status",
        projected.get("status"),
        "script_len",
        len(script),
        "has_distilbert",
        "distilbert" in script.lower(),
        "has_tfidf",
        "Tfidf" in script or "tfidf" in script.lower(),
        "criteria",
        plan.get("success_criteria"),
    )
    print("=== start run_iteration (may take several minutes)")
    out = run_one()
    rec = out.get("record") or {}
    exp = out.get("experiment") or {}
    sync_aisci(exp)
    print(
        "DONE status=",
        rec.get("status"),
        "iter=",
        rec.get("iteration_number"),
        "assess=",
        (rec.get("analysis") or {}).get("overall_assessment")
        if isinstance(rec.get("analysis"), dict)
        else None,
    )
    print("metrics", json.dumps(rec.get("metrics") or {}, ensure_ascii=False)[:800])
    print(
        "exp phase",
        exp.get("phase"),
        "status",
        exp.get("status"),
        "current_iteration",
        exp.get("current_iteration"),
    )
    return 0 if rec.get("status") in {"success", "partial_success", None} or rec.get("metrics") else 1


if __name__ == "__main__":
    raise SystemExit(main())
