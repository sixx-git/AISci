#!/usr/bin/env python3
"""Generate synthetic HFL Non-IID tabular CSV + quick metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=5)
    ap.add_argument("--rows", type=int, default=400)
    ap.add_argument("--skew", type=float, default=0.8)
    ap.add_argument("--out_csv", default="synthetic_hfl.csv")
    ap.add_argument("--out_metrics", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    rows = []
    for i in range(args.rows):
        c = i % args.clients
        # label skew: client prefers its own label
        if rng.random() < args.skew:
            label = c % 2
        else:
            label = int(rng.integers(0, 2))
        x = rng.normal(loc=label, size=3)
        rows.append(
            {
                "client_id": f"c{c}",
                "sample_id": f"s{i}",
                "x1": float(x[0]),
                "x2": float(x[1]),
                "x3": float(x[2]),
                "label": int(label),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(args.out_csv, index=False)
    metrics = {
        "num_clients": args.clients,
        "rows": len(df),
        "non_iid_type": "label_skew",
        "non_iid_degree": args.skew,
        "primary_metric": float(df["label"].mean()),
        "note": "partition helper for HFL pilots",
    }
    Path(args.out_metrics).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
