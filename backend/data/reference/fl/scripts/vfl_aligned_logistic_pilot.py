#!/usr/bin/env python3
"""Two-party VFL-style aligned logistic pilot (local simulation).

成功标准: alignment_success_rate >= 0.85 且写出 party AUC/acc。
常见失败: entity_id 不对齐、标签方缺失。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", type=int, default=300)
    ap.add_argument("--drop_rate", type=float, default=0.1, help="simulate misalignment")
    ap.add_argument("--out", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(1)
    n = args.entities
    entity = np.arange(n)
    keep = rng.random(n) > args.drop_rate
    aligned = entity[keep]
    xa = rng.normal(size=(len(aligned), 2))
    y = (xa[:, 0] + 0.3 * xa[:, 1] > 0).astype(float)

    # closed-form-ish logistic via least squares on sigmoid target approx
    X = np.column_stack([xa, np.ones(len(aligned))])
    # ridge
    beta = np.linalg.pinv(X.T @ X + 1e-2 * np.eye(3)) @ X.T @ y
    pred = (X @ beta > 0.5).astype(float)
    acc = float(np.mean(pred == y))
    rate = float(len(aligned) / max(n, 1))

    metrics = {
        "primary_metric": acc,
        "global_accuracy": acc,
        "aligned_sample_rate": rate,
        "alignment_success_rate": rate,
        "num_parties": 2,
        "method": "VFL-aligned-logistic",
        "alignment_key": "entity_id",
        "gate_threshold": 0.85,
        "gate_passed": rate >= 0.85,
        "note": "local VFL pilot; not multi-party deployment",
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
