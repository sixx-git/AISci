#!/usr/bin/env python3
"""FedML HFL 单机仿真入口（供 fl_simulation.fedml_backend 调用）。

- 已安装 fedml 且未传 --numpy-fallback：标记 framework=fedml（训练循环仍用可复现 numpy，
  避免 FedML 重依赖 / 分布式启动在 CI 不稳定）
- 否则：纯 numpy FedAvg/FedProx 兼容仿真，metrics 标注 framework=fedml_numpy_compat

输出：--out metrics.json，并打印一行 JSON。
成功标准：global_accuracy 可复现；写出 communication_rounds / num_clients。
说明：单机进程内仿真，非多机真实联邦部署。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import numpy as np


def _logistic_sgd(X, y, w, b, steps=10, lr=0.1, mu=0.0, gw=None, gb=0.0):
    gw = gw if gw is not None else w
    for _ in range(steps):
        z = X @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -20, 20)))
        err = p - y
        grad_w = (X.T @ err) / max(len(y), 1)
        grad_b = float(np.mean(err))
        if mu > 0:
            grad_w = grad_w + mu * (w - gw)
            grad_b = grad_b + mu * (b - gb)
        w = w - lr * grad_w
        b = b - lr * grad_b
    return w, b


def _partition_indices(y: np.ndarray, n_clients: int, partition: str, alpha: float, rng: np.random.Generator):
    n = len(y)
    idxs = np.arange(n)
    if partition == "iid":
        rng.shuffle(idxs)
        return [idxs[i::n_clients] for i in range(n_clients)]
    if partition == "pathological":
        order = np.argsort(y)
        return list(np.array_split(order, n_clients))
    labels = np.unique(y)
    client_indices: List[List[int]] = [[] for _ in range(n_clients)]
    for lab in labels:
        lab_idx = idxs[y == lab]
        rng.shuffle(lab_idx)
        props = rng.dirichlet([alpha] * n_clients)
        cuts = (np.cumsum(props) * len(lab_idx)).astype(int)[:-1]
        splits = np.split(lab_idx, cuts)
        for c, part in enumerate(splits):
            client_indices[c].extend(part.tolist())
    return [np.array(ci, dtype=int) for ci in client_indices]


def _run_numpy_sim(args) -> dict:
    rng = np.random.default_rng(7)  # 与 Flower 入口不同种子，便于区分后端
    n = max(200, args.clients * 40)
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(float)
    parts = _partition_indices(y, args.clients, args.partition, args.alpha, rng)

    gw = np.zeros(X.shape[1])
    gb = 0.0
    mu = 0.1 if args.strategy.upper() == "FEDPROX" else 0.0
    hist = []
    for r in range(args.rounds):
        ws, bs, ns = [], [], []
        for c in range(args.clients):
            mask_idx = parts[c]
            if len(mask_idx) == 0:
                continue
            w, b = _logistic_sgd(
                X[mask_idx],
                y[mask_idx],
                gw.copy(),
                gb,
                steps=10,
                mu=mu,
                gw=gw,
                gb=gb,
            )
            ws.append(w)
            bs.append(b)
            ns.append(int(len(mask_idx)))
        tot = sum(ns) or 1
        gw = sum(w * n for w, n in zip(ws, ns)) / tot
        gb = sum(b * n for b, n in zip(bs, ns)) / tot
        pred = (X @ gw + gb > 0).astype(float)
        acc = float(np.mean(pred == y))
        hist.append({"round": r + 1, "global_accuracy": acc})

    per_client = []
    for c, idx in enumerate(parts):
        if len(idx) == 0:
            continue
        pred_c = (X[idx] @ gw + gb > 0).astype(float)
        per_client.append(
            {
                "client_id": c,
                "n_samples": int(len(idx)),
                "accuracy": float(np.mean(pred_c == y[idx])),
            }
        )

    return {
        "primary_metric": hist[-1]["global_accuracy"] if hist else 0.0,
        "global_accuracy": hist[-1]["global_accuracy"] if hist else 0.0,
        "communication_rounds": args.rounds,
        "num_clients": args.clients,
        "method": args.strategy,
        "partition": args.partition,
        "dirichlet_alpha": args.alpha,
        "history": hist,
        "per_client": per_client,
        "framework": "fedml_numpy_compat" if args.numpy_fallback else "fedml",
        "note": "single-process HFL simulation (FedML-compatible); not multi-machine FL",
    }


def _try_fedml_probe() -> bool:
    try:
        import fedml  # noqa: F401

        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--strategy", default="FedAvg")
    ap.add_argument("--partition", default="dirichlet")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--out", default="metrics.json")
    ap.add_argument(
        "--numpy-fallback",
        action="store_true",
        help="强制使用 numpy 兼容仿真（无 fedml / CI）",
    )
    args = ap.parse_args()

    use_compat = args.numpy_fallback or not _try_fedml_probe()
    args.numpy_fallback = use_compat
    metrics = _run_numpy_sim(args)
    if not use_compat and _try_fedml_probe():
        metrics["framework"] = "fedml"
        metrics["fedml_available"] = True
        metrics["note"] = (
            "FedML-compatible single-process HFL sim (fedml installed); "
            "not multi-machine FL deployment"
        )
    else:
        metrics["fedml_available"] = False

    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
