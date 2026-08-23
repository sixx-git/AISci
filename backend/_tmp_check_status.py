# -*- coding: utf-8 -*-
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

db = Path(r"d:\Workplace\AISci\backend\data\aiscientist.db")
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("=== tables ===")
print("\n".join(tables))

pid = "6dbf4b5a-034b-4a63-a8bd-2c601588f477"
print("\n=== project ===")
proj = cur.execute("SELECT id, name, status, research_question FROM projects WHERE id=?", (pid,)).fetchone()
if proj:
    print(dict(proj))

print("\n=== iterative experiments JSON ===")
ie_root = Path(r"d:\Workplace\AISci\backend\storage\iterative_experiments") / pid
print("path exists:", ie_root.exists(), ie_root)
if ie_root.exists():
    for p in sorted(ie_root.rglob("*")):
        if p.is_file():
            print(" file:", p.relative_to(ie_root), "size=", p.stat().st_size)

    for p in sorted(ie_root.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            print(f"\n{p.name}: {len(data)} experiments")
            for e in data[-5:]:
                print(
                    " -",
                    e.get("id"),
                    "phase=",
                    e.get("phase"),
                    "title=",
                    str(e.get("title") or e.get("hypothesis") or "")[:60],
                    "job=",
                    e.get("job_status") or e.get("async_job"),
                )
        elif isinstance(data, dict):
            print(f"\n{p.name}: keys={list(data.keys())[:20]}")
            if "experiments" in data:
                for e in data["experiments"][-5:]:
                    print(" -", e.get("id"), "phase=", e.get("phase"))
            else:
                print(" phase=", data.get("phase"), "id=", data.get("id"))

print("\n=== audit log tail ===")
audit = Path(r"d:\Workplace\AISci\backend\storage\audit") / f"{pid}.jsonl"
# try run-based audit
audit2 = Path(r"d:\Workplace\AISci\backend\storage\audit") / "63221edb-6d29-4be4-96ac-6e8a104adf19.jsonl"
for a in (audit, audit2):
    if a.exists():
        lines = a.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        print(a.name, "lines=", len(lines))
        for line in lines[-8:]:
            try:
                ev = json.loads(line)
                print(" ", ev.get("event") or ev.get("type"), str(ev)[:200])
            except Exception:
                print(" ", line[:200])

# shaxiang db if any
print("\n=== shaxiang dbs ===")
for p in Path(r"d:\Workplace\AISci").rglob("*.db"):
    if "shaxiang" in str(p).lower() or "experiment" in str(p).lower():
        print(p)
