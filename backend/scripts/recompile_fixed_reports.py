"""重编译 storage/reports 下已有 report.tex 的 PDF。"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.latex_export_service import compile_latex_to_pdf  # noqa: E402

REPORTS_DIR = BACKEND_ROOT / "storage" / "reports"


def main() -> None:
    folders = sorted([d for d in REPORTS_DIR.iterdir() if d.is_dir()], key=lambda p: p.name)
    ok = fail = skip = 0
    for folder in folders:
        tex = folder / "report.tex"
        if not tex.exists():
            skip += 1
            continue
        result = compile_latex_to_pdf(folder, "report.tex")
        if result.get("success"):
            ok += 1
            print(f"[pdf-ok] {folder.name}")
        else:
            fail += 1
            print(f"[pdf-fail] {folder.name}: {result.get('warning')}")
    print("DONE", {"ok": ok, "fail": fail, "skip": skip})


if __name__ == "__main__":
    main()
