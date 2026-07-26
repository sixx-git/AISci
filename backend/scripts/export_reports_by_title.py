"""将 storage/reports 下 PDF 按报告题目导出到目标目录。"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC = BACKEND_ROOT / "storage" / "reports"
DEFAULT_DST = Path(r"D:\浏览器\报告1")


def safe_name(title: str) -> str:
    title = (title or "").strip()
    title = re.sub(r'[<>:"/\\|?*]', "_", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    return (title or "untitled")[:180]


def resolve_title(folder: Path) -> str:
    jp = folder / "report_data.json"
    if jp.exists():
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            title = (data.get("paper_title") or data.get("title") or "").strip()
            if title:
                return title
        except (json.JSONDecodeError, OSError):
            pass
    tex = folder / "report.tex"
    if tex.exists():
        text = tex.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"\\title\{(.+?)\}", text, flags=re.S)
        if m:
            raw = m.group(1)
            raw = re.sub(r"\\[a-zA-Z]+\*?", "", raw)
            raw = raw.replace("{", "").replace("}", "")
            raw = re.sub(r"\s+", " ", raw).strip()
            if raw:
                return raw
    return folder.name


def main() -> None:
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DST
    dst.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    used: dict[str, int] = {}

    for folder in sorted(p for p in SRC.iterdir() if p.is_dir()):
        pdf = folder / "report.pdf"
        if not pdf.exists() or pdf.stat().st_size <= 0:
            skipped += 1
            continue
        name = safe_name(resolve_title(folder))
        n = used.get(name, 0)
        used[name] = n + 1
        filename = f"{name}.pdf" if n == 0 else f"{name}_{n + 1}.pdf"
        out = dst / filename
        shutil.copy2(pdf, out)
        copied += 1
        print(f"OK {folder.name} -> {filename}")

    print(
        "DONE",
        {
            "copied": copied,
            "skipped_no_pdf": skipped,
            "dest": str(dst),
            "files_in_dest": len(list(dst.glob("*.pdf"))),
        },
    )


if __name__ == "__main__":
    main()
