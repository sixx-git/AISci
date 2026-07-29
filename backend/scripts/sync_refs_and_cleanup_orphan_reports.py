"""同步最新报告参考文献到 DB，并删除非 125 项目的孤儿报告。"""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "aiscientist.db"
REPORTS = BACKEND / "storage" / "reports"


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _refs_from_folder(folder_id: str) -> Optional[List[str]]:
    data = _load_json(REPORTS / str(folder_id) / "report_data.json")
    if not data:
        return None
    chapters = data.get("chapters") if isinstance(data.get("chapters"), dict) else {}
    refs = chapters.get("references") or data.get("references")
    if isinstance(refs, list):
        return [str(x).strip() for x in refs if str(x).strip()]
    if isinstance(refs, str) and refs.strip():
        try:
            parsed = json.loads(refs)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            return [refs.strip()]
    return None


def sync_references(conn: sqlite3.Connection) -> Dict[str, int]:
    """将 storage/report_data.json 的 references 写回 reports.\"references\"。"""
    rows = conn.execute(
        """
        select r.id, r.pdf_path
        from reports r
        join projects p on p.id = r.project_id
        """
    ).fetchall()
    stats = {"total": 0, "updated": 0, "missing_json": 0, "unchanged": 0}
    for row in rows:
        stats["total"] += 1
        folder_id = row["pdf_path"] or row["id"]
        refs = _refs_from_folder(str(folder_id))
        if refs is None:
            stats["missing_json"] += 1
            continue
        refs_json = json.dumps(refs, ensure_ascii=False)
        old = conn.execute(
            'select "references" as refs from reports where id=?',
            (row["id"],),
        ).fetchone()["refs"]
        if old == refs_json:
            stats["unchanged"] += 1
            continue
        conn.execute(
            'update reports set "references" = ?, updated_at = datetime(\'now\') where id = ?',
            (refs_json, row["id"]),
        )
        stats["updated"] += 1
    conn.commit()
    return stats


def delete_orphan_reports(conn: sqlite3.Connection, *, remove_files: bool) -> Dict[str, Any]:
    """删除 project_id 不在 projects 表中的报告（旧项目残留）。"""
    orph = conn.execute(
        """
        select r.id, r.project_id, r.pdf_path, r.paper_title, r.created_at
        from reports r
        left join projects p on p.id = r.project_id
        where p.id is null
        """
    ).fetchall()
    deleted_ids: List[str] = []
    removed_dirs: List[str] = []
    for row in orph:
        rid = row["id"]
        folder_id = row["pdf_path"] or rid
        conn.execute("delete from reports where id = ?", (rid,))
        deleted_ids.append(rid)
        if remove_files and folder_id:
            folder = REPORTS / str(folder_id)
            if folder.is_dir():
                shutil.rmtree(folder, ignore_errors=True)
                removed_dirs.append(str(folder_id))
            # 若 pdf_path 与 id 不同，id 目录也可能存在
            if row["pdf_path"] and row["pdf_path"] != rid:
                id_folder = REPORTS / rid
                if id_folder.is_dir():
                    shutil.rmtree(id_folder, ignore_errors=True)
                    removed_dirs.append(rid)
    conn.commit()
    return {
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "removed_dirs": removed_dirs,
        "details": [dict(r) for r in orph],
    }


def prune_unreferenced_storage(conn: sqlite3.Connection) -> List[str]:
    """删除磁盘上未被任何 reports.id / pdf_path 引用的报告目录。"""
    keep: set[str] = set()
    for row in conn.execute("select id, pdf_path from reports"):
        keep.add(row["id"])
        if row["pdf_path"]:
            keep.add(str(row["pdf_path"]))
    removed: List[str] = []
    if not REPORTS.is_dir():
        return removed
    for d in list(REPORTS.iterdir()):
        if not d.is_dir():
            continue
        if d.name in keep:
            continue
        shutil.rmtree(d, ignore_errors=True)
        removed.append(d.name)
    return removed


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    n_projects = conn.execute("select count(*) c from projects").fetchone()["c"]
    n_reports_before = conn.execute("select count(*) c from reports").fetchone()["c"]
    print(f"before projects={n_projects} reports={n_reports_before}")

    sync_stats = sync_references(conn)
    print("sync_references", sync_stats)

    orphan_stats = delete_orphan_reports(conn, remove_files=True)
    print("delete_orphan_reports", orphan_stats)

    pruned = prune_unreferenced_storage(conn)
    print(f"pruned_unreferenced_dirs={len(pruned)}")
    if pruned:
        print("  sample", pruned[:15])

    n_reports_after = conn.execute("select count(*) c from reports").fetchone()["c"]
    orphan_left = conn.execute(
        """
        select count(*) c from reports r
        left join projects p on p.id=r.project_id where p.id is null
        """
    ).fetchone()["c"]
    # mismatch check on latest
    rows = conn.execute(
        """
        select r.id, r.project_id, r.pdf_path, r.created_at, r.version, r."references" as refs
        from reports r join projects p on p.id=r.project_id
        """
    ).fetchall()

    def key(r):
        created = str(r["created_at"] or "")
        try:
            version = int(r["version"] or 0)
        except (TypeError, ValueError):
            version = 0
        return (created, version, str(r["id"]))

    latest: Dict[str, Any] = {}
    for r in rows:
        pid = r["project_id"]
        prev = latest.get(pid)
        if prev is None or key(r) > key(prev):
            latest[pid] = r

    mismatch = 0
    for r in latest.values():
        folder_id = r["pdf_path"] or r["id"]
        file_refs = _refs_from_folder(str(folder_id)) or []
        try:
            db_refs = json.loads(r["refs"]) if r["refs"] else []
        except json.JSONDecodeError:
            db_refs = []
        if db_refs != file_refs:
            mismatch += 1

    print(
        f"after projects={n_projects} reports={n_reports_after} "
        f"orphan_left={orphan_left} latest_ref_mismatch={mismatch}"
    )
    conn.close()


if __name__ == "__main__":
    main()
