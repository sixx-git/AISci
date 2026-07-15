#!/usr/bin/env python3
"""对比生成评分表与人工样例（主张核查）。"""
import json
import re
import sys
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent


def load(p):
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return json.loads(p.read_text(encoding=enc))
        except Exception:
            pass
    raise ValueError(p)


def analyze(path):
    d = load(path)
    dims = {dim["dimension_id"]: dim for dim in d["rubrics"]["dimensions"]}
    all_items = []
    for dim in dims.values():
        all_items.extend(dim["items"])
    sr = dims.get("scientific_reasoning", {}).get("items", [])
    sy = dims.get("report_synthesis", {}).get("items", [])
    sr_verbs = Counter()
    claim = 0
    for it in sr:
        m = re.search(r"Does the report ([a-z]+)", it["question"], re.I)
        if m:
            sr_verbs[m.group(1).lower()] += 1
        if re.search(r"claim|verdict|evidence|sub-proposition|assertion|refut", it["question"], re.I):
            claim += 1
    return {
        "total": d["rubrics"]["total_score"],
        "items": len(all_items),
        "task_type": d.get("task_type"),
        "ia": len(dims["information_acquisition"]["items"]),
        "sr": len(sr),
        "sy": len(sy),
        "sr_crit": sum(1 for it in sr if it["role"] == "Critical"),
        "sy_crit": sum(1 for it in sy if it["role"] == "Critical"),
        "sy_mand": sum(1 for it in sy if it["role"] == "Mandatory"),
        "sy_src": sum(1 for it in sy if it.get("source_ids")) / max(len(sy), 1),
        "sr_multi": sum(1 for it in sr if len(it.get("source_ids") or []) >= 2) / max(len(sr), 1),
        "sr_claim_pct": claim / max(len(sr), 1),
        "sr_verbs": sr_verbs.most_common(5),
        "explain_pct": sr_verbs.get("explain", 0) / max(len(sr), 1),
    }


def main():
    gen_path = Path(sys.argv[1])
    sample_path = BASE / "样例/Deep交付模板/主张核查报告/task.json"
    g, s = analyze(gen_path), analyze(sample_path)
    print(f"Generated: {gen_path}")
    print(f"  total={g['total']} items={g['items']} type={g['task_type']}")
    print(f"  IA={g['ia']} SR={g['sr']}(C={g['sr_crit']}, claim={g['sr_claim_pct']:.0%}, multi={g['sr_multi']:.0%})")
    print(f"  Synth={g['sy']}(M={g['sy_mand']}, C={g['sy_crit']}, src={g['sy_src']:.0%})")
    print(f"  SR verbs: {g['sr_verbs']}, explain={g['explain_pct']:.0%}")
    print(f"Sample: total={s['total']} items={s['items']}")
    print(f"  IA={s['ia']} SR={s['sr']}(C={s['sr_crit']}) Synth={s['sy']}(M={s['sy_mand']}, C={s['sy_crit']})")


if __name__ == "__main__":
    main()
