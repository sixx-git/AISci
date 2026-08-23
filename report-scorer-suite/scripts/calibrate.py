#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report-scientist-scorer 配套：把科学家评分表的总分列校准到目标均值(默认85)，
使科学家版与客观版(report-weighted-scorer)处于同一量尺，便于直接对比。
用法:
  python calibrate.py --csv <scientist_scores.csv> [--col 总分] [--target-mean 85] [--out <校准后csv>]
"""
import argparse, csv, statistics

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--col", default="总分")
    ap.add_argument("--target-mean", type=float, default=85.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    if args.col not in rows[0]:
        sys.exit(f"列 {args.col} 不存在，可选: {list(rows[0].keys())}")
    vals = [float(r[args.col]) for r in rows]
    base_mean = statistics.mean(vals)
    offset = round(args.target_mean - base_mean, 2)
    cal_col = args.col + "_cal"
    for r in rows:
        r[cal_col] = round(min(100.0, max(0.0, float(r[args.col]) + offset)), 1)

    out = args.out or args.csv.replace(".csv", "_calibrated.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=rows[0].keys()); w.writeheader()
        for r in rows: w.writerow(r)

    cal_vals = [float(r[cal_col]) for r in rows]
    print(f"原均值 {base_mean:.2f} | 校准平移 +{offset} | 校准后均值 {statistics.mean(cal_vals):.1f}")
    print("输出 ->", out)

if __name__ == "__main__":
    import sys
    main()
