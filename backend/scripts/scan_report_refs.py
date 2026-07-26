"""扫描 storage/reports 中脏引用。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "storage" / "reports"

MARKERS = ("<i>", "</i>", "{[J]}", "{[M]}", "{[J/OL]}", "{[EB/OL]}", r"\{[J]\}", r"\{[M]\}")


def main() -> None:
    dirs = [d for d in ROOT.iterdir() if d.is_dir()]
    print("dirs", len(dirs))
    bad_tex = []
    bad_json = []
    for d in dirs:
        tex = d / "report.tex"
        if tex.exists():
            t = tex.read_text(encoding="utf-8", errors="replace")
            hits = [m for m in MARKERS if m in t]
            if re.search(r"\\\{\[[A-Z]", t):
                hits.append("escaped_type")
            if hits:
                bad_tex.append((d.name, hits))
        jp = d / "report_data.json"
        if not jp.exists():
            continue
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            continue
        ch = data.get("chapters") or {}
        refs = ch.get("references") or data.get("references") or []
        if isinstance(refs, str):
            refs = [refs]
        blob = "\n".join(str(r) for r in refs if r)
        hits = [m for m in ("<i>", "{[J]}", "{[M]}", "{[J/OL]}", "[J][J]") if m in blob]
        if hits:
            bad_json.append((d.name, hits, blob[:240].replace("\n", " | ")))

    print("bad_tex", len(bad_tex))
    for x in bad_tex[:20]:
        print(" TEX", x)
    print("bad_json", len(bad_json))
    for x in bad_json[:10]:
        print(" JSON", x[0], x[1], x[2])


if __name__ == "__main__":
    main()
