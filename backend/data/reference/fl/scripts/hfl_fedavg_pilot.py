#!/usr/bin/env python3
"""HFL FedAvg pilot (local simulation, no Flower).

适用边界: 表格二分类；客户端按 client_id 划分。
成功标准: global_accuracy 可复现；写出 communication_rounds。
常见失败: 客户端样本过少、标签全偏到一侧。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _logistic_sgd(X, y, steps=20, lr=0.1):
    w = np.zeros(X.shape[1])
    b = 0.0
    for _ in range(steps):
        z = X @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -20, 20)))
        err = p - y
        w -= lr * (X.T @ err) / max(len(y), 1)
        b -= lr * float(np.mean(err))
    return w, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="", help="optional CSV with client_id, features, label")
    ap.add_argument("--clients", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(42)
    n = 200
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(float)
    client_ids = np.array([i % args.clients for i in range(n)])

    gw = np.zeros(X.shape[1])
    gb = 0.0
    hist = []
    for r in range(args.rounds):
        ws, bs, ns = [], [], []
        for c in range(args.clients):
            mask = client_ids == c
            if not np.any(mask):
                continue
            w, b = _logistic_sgd(X[mask], y[mask], steps=10)
            # one local step toward global init mix
            w = 0.5 * w + 0.5 * gw
            b = 0.5 * b + 0.5 * gb
            ws.append(w)
            bs.append(b)
            ns.append(int(mask.sum()))
        tot = sum(ns) or 1
        gw = sum(w * n for w, n in zip(ws, ns)) / tot
        gb = sum(b * n for b, n in zip(bs, ns)) / tot
        pred = (X @ gw + gb > 0).astype(float)
        acc = float(np.mean(pred == y))
        hist.append({"round": r + 1, "global_accuracy": acc})

    metrics = {
        "primary_metric": hist[-1]["global_accuracy"] if hist else 0.0,
        "global_accuracy": hist[-1]["global_accuracy"] if hist else 0.0,
        "communication_rounds": args.rounds,
        "num_clients": args.clients,
        "method": "FedAvg",
        "history": hist,
        "note": "local HFL pilot; not multi-machine FL",
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
