# -*- coding: utf-8 -*-
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

sx = Path(r"d:\Workplace\AISci\shaxiang-main\shaxiang-main\data\experiments.db")
con = sqlite3.connect(sx)
con.row_factory = sqlite3.Row
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
    print(f"\n=== {t} cols={cols} ===")
    try:
        rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 8").fetchall()
    except Exception as e:
        print("query err", e)
        continue
    for r in rows:
        d = dict(r)
        # trim long fields
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 120:
                d[k] = v[:120] + "..."
        print(d)

# jobs storage
print("\n=== iterative experiment jobs ===")
root = Path(r"d:\Workplace\AISci\backend\storage")
for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue
    name = p.name.lower()
    if "job" in name or "iterative" in str(p).lower():
        print(p, p.stat().st_size)

jobs_dir = Path(r"d:\Workplace\AISci\backend\storage\iterative_experiment_jobs")
print("jobs_dir exists", jobs_dir.exists())
if jobs_dir.exists():
    for p in sorted(jobs_dir.rglob("*"))[:30]:
        print(p)
