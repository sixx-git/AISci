#!/usr/bin/env python3
"""Compare Local / Centralized / FedAvg / FedProx on Dirichlet-partitioned tabular data.

默认档位: 标准 Non-IID（Dirichlet α=0.1）+ FedProx μ 对比。
成功标准: metrics.json 含 methods 对比表、partition_method、communication_rounds。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _logistic_sgd(X, y, w=None, b=0.0, steps=20, lr=0.1, prox_mu=0.0, w_global=None, b_global=0.0):
    w = np.zeros(X.shape[1]) if w is None else w.copy()
    b = float(b)
    wg = w_global if w_global is not None else w
    for _ in range(steps):
        z = X @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -20, 20)))
        err = p - y
        grad_w = (X.T @ err) / max(len(y), 1) + prox_mu * (w - wg)
        grad_b = float(np.mean(err)) + prox_mu * (b - b_global)
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def _acc(X, y, w, b):
    pred = (X @ w + b > 0).astype(float)
    return float(np.mean(pred == y))


def _make_dirichlet_data(n_clients, n_rows, alpha, seed, n_classes=2):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n_rows, 4))
    y = (X[:, 0] + 0.3 * X[:, 1] > 0).astype(float)
    # binary dirichlet by soft assignment via alpha-skewed client preference
    client_ids = np.zeros(n_rows, dtype=int)
    for lab in (0, 1):
        idx = np.where(y == lab)[0]
        rng.shuffle(idx)
        props = rng.dirichlet([alpha] * n_clients)
        cuts = (np.cumsum(props) * len(idx)).astype(int)[:-1]
        for c, part in enumerate(np.split(idx, cuts)):
            client_ids[part] = c
    return X, y, client_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=20)
    ap.add_argument("--rows", type=int, default=800)
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--local_epochs", type=int, default=5)
    ap.add_argument("--participation", type=float, default=0.2)
    ap.add_argument("--mu", type=float, default=0.01, help="FedProx proximal coefficient")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="metrics.json")
    args = ap.parse_args()

    X, y, client_ids = _make_dirichlet_data(args.clients, args.rows, args.alpha, args.seed)
    rng = np.random.default_rng(args.seed)

    # Centralized
    w_c, b_c = _logistic_sgd(X, y, steps=args.local_epochs * 10)
    acc_central = _acc(X, y, w_c, b_c)

    # Local-only: average of per-client models evaluated globally
    local_accs = []
    for c in range(args.clients):
        mask = client_ids == c
        if not np.any(mask):
            continue
        w_l, b_l = _logistic_sgd(X[mask], y[mask], steps=args.local_epochs * 5)
        local_accs.append(_acc(X, y, w_l, b_l))
    acc_local = float(np.mean(local_accs)) if local_accs else 0.0

    def run_federated(prox_mu: float):
        gw = np.zeros(X.shape[1])
        gb = 0.0
        hist = []
        k = max(1, int(args.clients * args.participation))
        for r in range(args.rounds):
            chosen = rng.choice(args.clients, size=min(k, args.clients), replace=False)
            ws, bs, ns = [], [], []
            for c in chosen:
                mask = client_ids == c
                if not np.any(mask):
                    continue
                w, b = _logistic_sgd(
                    X[mask],
                    y[mask],
                    w=gw,
                    b=gb,
                    steps=args.local_epochs,
                    prox_mu=prox_mu,
                    w_global=gw,
                    b_global=gb,
                )
                ws.append(w)
                bs.append(b)
                ns.append(int(mask.sum()))
            if ws:
                tot = sum(ns) or 1
                gw = sum(w * n for w, n in zip(ws, ns)) / tot
                gb = sum(b * n for b, n in zip(bs, ns)) / tot
            hist.append({"round": r + 1, "global_accuracy": _acc(X, y, gw, gb)})
        return hist, gw, gb

    hist_avg, gw_a, gb_a = run_federated(0.0)
    hist_prox, gw_p, gb_p = run_federated(args.mu)

    # client_drift on final FedAvg
    drifts = []
    for c in range(args.clients):
        mask = client_ids == c
        if np.any(mask):
            drifts.append(_acc(X[mask], y[mask], gw_a, gb_a))
    client_drift = float(np.std(drifts)) if drifts else 0.0

    methods = {
        "local_only": {"global_accuracy": acc_local},
        "centralized": {"global_accuracy": acc_central},
        "FedAvg": {
            "global_accuracy": hist_avg[-1]["global_accuracy"] if hist_avg else 0.0,
            "communication_rounds": args.rounds,
            "history": hist_avg,
        },
        "FedProx": {
            "global_accuracy": hist_prox[-1]["global_accuracy"] if hist_prox else 0.0,
            "communication_rounds": args.rounds,
            "mu": args.mu,
            "history": hist_prox,
        },
    }
    primary = methods["FedProx"]["global_accuracy"]
    metrics = {
        "primary_metric": primary,
        "global_accuracy": primary,
        "methods": methods,
        "partition_method": "dirichlet",
        "non_iid_type": "dirichlet",
        "non_iid_degree": float(1.0 / max(args.alpha, 1e-6)),
        "alpha": args.alpha,
        "num_clients": args.clients,
        "participation_rate": args.participation,
        "local_epochs": args.local_epochs,
        "communication_rounds": args.rounds,
        "client_drift": client_drift,
        "fedprox_mu": args.mu,
        "seed": args.seed,
        "baselines": ["local_only", "centralized", "FedAvg", "FedProx"],
        "note": "standard Non-IID baseline compare; local simulation only",
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in metrics if k != "methods"}))
    print(json.dumps({"methods_summary": {m: methods[m].get("global_accuracy") for m in methods}}))


if __name__ == "__main__":
    main()
