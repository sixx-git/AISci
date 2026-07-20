#!/usr/bin/env python3
"""Dirichlet / pathological Non-IID partition for HFL pilots (local only).

默认档位: Dirichlet α=0.1，20 clients。
成功标准: 写出 partition_method / alpha / non_iid_degree 与 CSV。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _dirichlet_partition(y: np.ndarray, n_clients: int, alpha: float, rng: np.random.Generator):
    labels = np.unique(y)
    client_indices = [[] for _ in range(n_clients)]
    for lab in labels:
        idx = np.where(y == lab)[0]
        rng.shuffle(idx)
        props = rng.dirichlet([alpha] * n_clients)
        cuts = (np.cumsum(props) * len(idx)).astype(int)[:-1]
        splits = np.split(idx, cuts)
        for c, part in enumerate(splits):
            client_indices[c].extend(part.tolist())
    return client_indices


def _pathological_partition(y: np.ndarray, n_clients: int, k: int, rng: np.random.Generator):
    labels = list(np.unique(y))
    rng.shuffle(labels)
    client_indices = [[] for _ in range(n_clients)]
    for c in range(n_clients):
        labs = labels[(c * k) % len(labels) : (c * k) % len(labels) + k]
        if len(labs) < k:
            labs = (labels + labels)[:k]
        for lab in labs:
            idx = np.where(y == lab)[0]
            take = idx[rng.choice(len(idx), size=max(1, len(idx) // n_clients), replace=False)]
            client_indices[c].extend(take.tolist())
    return client_indices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dirichlet", "pathological", "quantity"], default="dirichlet")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--clients", type=int, default=20)
    ap.add_argument("--rows", type=int, default=800)
    ap.add_argument("--n_classes", type=int, default=4)
    ap.add_argument("--classes_per_client", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_csv", default="synthetic_dirichlet_hfl.csv")
    ap.add_argument("--out_metrics", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    X = rng.normal(size=(args.rows, 4))
    # synthetic multi-class labels correlated with first feature
    y = np.clip(((X[:, 0] + 2) * args.n_classes / 4).astype(int), 0, args.n_classes - 1)

    if args.mode == "pathological":
        parts = _pathological_partition(y, args.clients, args.classes_per_client, rng)
        partition_method = "pathological"
        non_iid_degree = 1.0
    else:
        parts = _dirichlet_partition(y, args.clients, args.alpha, rng)
        partition_method = "dirichlet"
        non_iid_degree = float(1.0 / max(args.alpha, 1e-6))

    # quantity skew: resample client sizes via Dirichlet
    if args.mode == "quantity":
        sizes = rng.dirichlet([args.alpha] * args.clients)
        sizes = (sizes * args.rows).astype(int)
        sizes[-1] = args.rows - sizes[:-1].sum()
        order = rng.permutation(args.rows)
        parts = []
        start = 0
        for s in sizes:
            parts.append(order[start : start + max(s, 0)].tolist())
            start += max(s, 0)
        partition_method = "quantity_skew"
        non_iid_degree = float(np.std([len(p) for p in parts]) / max(np.mean([len(p) for p in parts]), 1))

    rows = []
    for c, idxs in enumerate(parts):
        for i in idxs:
            rows.append(
                {
                    "client_id": f"c{c}",
                    "sample_id": f"s{i}",
                    "x1": float(X[i, 0]),
                    "x2": float(X[i, 1]),
                    "x3": float(X[i, 2]),
                    "x4": float(X[i, 3]),
                    "label": int(y[i]),
                }
            )
    df = pd.DataFrame(rows)
    if args.mode == "quantity":
        pass
    df.to_csv(args.out_csv, index=False)

    # crude client_drift: variance of per-client label means
    drifts = []
    for c in range(args.clients):
        sub = df[df["client_id"] == f"c{c}"]["label"]
        if len(sub):
            drifts.append(float(sub.mean()))
    client_drift = float(np.std(drifts)) if drifts else 0.0

    metrics = {
        "primary_metric": client_drift,
        "partition_method": partition_method,
        "non_iid_type": partition_method,
        "non_iid_degree": non_iid_degree,
        "alpha": args.alpha if partition_method == "dirichlet" else None,
        "num_clients": args.clients,
        "rows": len(df),
        "client_drift": client_drift,
        "classes_per_client": args.classes_per_client if partition_method == "pathological" else None,
        "seed": args.seed,
        "note": "partition helper for standard Non-IID FL pilots",
    }
    Path(args.out_metrics).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
