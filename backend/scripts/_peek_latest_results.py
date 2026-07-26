from pathlib import Path
import json
import re

d = Path("storage/reports/a429c00b-ca60-4d08-9118-367ffa94d53f")
data = json.loads((d / "report_data.json").read_text(encoding="utf-8"))
results = (data.get("chapters") or {}).get("results") or ""
print("=== RESULTS TYPE", type(results))
if isinstance(results, dict):
    print(json.dumps(results, ensure_ascii=False, indent=2)[:4000])
else:
    text = str(results)
    print("--- markdown headings ---")
    for ln in text.splitlines():
        if ln.strip().startswith("#") or "”" in ln or '"' in ln or "“" in ln or "**" in ln[:20]:
            print(repr(ln[:200]))
    print("--- discussion slice ---")
    idx = text.find("结果分析")
    print(text[idx : idx + 2000] if idx >= 0 else text[:2000])

tex = (d / "report.tex").read_text(encoding="utf-8")
print("\n=== TEX subsections with quote-like ---")
for m in re.finditer(r"\\subsection\{([^}]*)\}", tex):
    title = m.group(1)
    if any(ch in title for ch in ['"', "“", "”", "。", "发现", "讨论", "结果", "局限", "意义"]):
        print(repr(title))
