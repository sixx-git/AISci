# -*- coding: utf-8 -*-
import json
import sqlite3
from pathlib import Path

db = Path(r"d:\Workplace\AISci\shaxiang-main\shaxiang-main\data\experiments.db")
conn = sqlite3.connect(str(db))
cur = conn.cursor()
rows = cur.execute(
    "SELECT id, phase, substr(hypothesis,1,50), data_config, current_data_config, updated_at "
    "FROM experiments ORDER BY updated_at DESC LIMIT 8"
).fetchall()
for r in rows:
    print("=" * 60)
    print("id", r[0], "phase", r[1], "updated", r[5])
    print("hyp", r[2])
    for label, raw in (("data_config", r[3]), ("current_data_config", r[4])):
        if not raw:
            print(label, None)
            continue
        try:
            d = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            print(label, "parse fail", e)
            continue
        print(label, "type=", d.get("source_type"), "path=", d.get("source_path"))
        print("  profile_name=", d.get("profile_name"), "cols=", len(d.get("columns") or []))
        pj = d.get("profile_json")
        if isinstance(pj, str) and pj.strip().startswith("{"):
            p = json.loads(pj)
            print("  profile=", {k: p.get(k) for k in ["name", "modality", "scan_pattern", "file_extensions", "delimiter", "has_header", "comment_prefix"]})
