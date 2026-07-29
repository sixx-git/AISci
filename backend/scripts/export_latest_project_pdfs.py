"""导出每个项目最新报告 PDF，文件名为论文题目，到指定目录。

最新判定：优先 created_at（新生成报告），再 version，再 updated_at，再 id。
注意：不可把 updated_at=NULL 当成最早，否则会误选旧版。
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "aiscientist.db"
REPORTS_DIR = BACKEND / "storage" / "reports"
DEFAULT_DST = Path(r"D:\浏览器\报告2")


def safe_name(title: str) -> str:
    title = (title or "").strip()
    title = re.sub(r'[<>:"/\\|?*]', "_", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    return (title or "untitled")[:180]


def resolve_pdf(pdf_path: str | None, report_id: str) -> Path | None:
    candidates: list[Path] = []
    if pdf_path:
        p = Path(pdf_path)
        candidates.append(p)
        if not p.is_absolute():
            candidates.append(BACKEND / pdf_path)
            candidates.append(BACKEND / "storage" / pdf_path)
    candidates.append(REPORTS_DIR / report_id / "report.pdf")
    if pdf_path:
        stem = Path(str(pdf_path).replace("\\", "/")).name
        if stem.endswith(".pdf"):
            candidates.append(REPORTS_DIR / Path(stem).stem / "report.pdf")
        else:
            candidates.append(REPORTS_DIR / stem / "report.pdf")
            candidates.append(REPORTS_DIR / stem)
    for c in candidates:
        try:
            if c.is_file() and c.stat().st_size > 0:
                return c
        except OSError:
            continue
    return None


def latest_key(row: sqlite3.Row) -> tuple:
    """越大越新。created_at 优先，避免 updated_at 批量回写把旧报告顶上来。"""
    created = str(row["created_at"] or "")
    updated = str(row["updated_at"] or "") or created
    try:
        version = int(row["version"] or 0)
    except (TypeError, ValueError):
        version = 0
    return (created, version, updated, str(row["id"]))


def main() -> None:
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DST
    clear = "--clear" in sys.argv
    dst.mkdir(parents=True, exist_ok=True)

    if not DB.exists():
        raise SystemExit(f"数据库不存在: {DB}")

    if clear:
        removed = 0
        for p in dst.glob("*.pdf"):
            p.unlink()
            removed += 1
        print(f"cleared_old_pdfs={removed}")

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS n FROM projects")
    n_projects = int(cur.fetchone()["n"])

    cur.execute(
        """
        SELECT r.id, r.project_id, r.paper_title, r.title, r.pdf_path,
               r.version, r.created_at, r.updated_at, p.name AS project_name
        FROM reports r
        JOIN projects p ON p.id = r.project_id
        """
    )
    rows = list(cur.fetchall())
    conn.close()

    latest: dict[str, sqlite3.Row] = {}
    for row in rows:
        pid = row["project_id"]
        prev = latest.get(pid)
        if prev is None or latest_key(row) > latest_key(prev):
            latest[pid] = row

    copied = 0
    missing_pdf = 0
    used_names: dict[str, int] = {}
    details: list[str] = []

    for _pid, row in sorted(latest.items(), key=lambda kv: str(kv[1]["project_name"] or "")):
        title = (row["paper_title"] or row["title"] or row["project_name"] or row["id"]).strip()
        pdf = resolve_pdf(row["pdf_path"], row["id"])
        if pdf is None:
            missing_pdf += 1
            details.append(
                f"MISS {row['project_name']} | v{row['version']} | {title[:60]} | id={row['id']}"
            )
            continue
        name = safe_name(title)
        n = used_names.get(name, 0)
        used_names[name] = n + 1
        filename = f"{name}.pdf" if n == 0 else f"{name}_{n + 1}.pdf"
        out = dst / filename
        shutil.copy2(pdf, out)
        copied += 1
        details.append(
            f"OK {row['project_name']} | v{row['version']} | created={row['created_at']} -> {filename}"
        )

    print(f"projects_in_db={n_projects}")
    print(f"projects_with_report={len(latest)}")
    print(f"copied={copied}")
    print(f"missing_pdf={missing_pdf}")
    print(f"dest={dst}")
    print(f"files_in_dest={len(list(dst.glob('*.pdf')))}")
    for line in details:
        print(line)


if __name__ == "__main__":
    main()
