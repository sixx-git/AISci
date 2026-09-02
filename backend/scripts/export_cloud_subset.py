"""
将指定本地项目 + 报告产物 + 迭代实验（shaxiang）导出为云端可恢复包：
- backend/data/export_cloud/aiscientist.db
- backend/data/export_cloud/reports_bundle.tar.gz
- backend/data/export_cloud/iterative_experiments_bundle.tar.gz
- backend/data/export_cloud/shaxiang_data_bundle.tar.gz
"""
from __future__ import annotations

import json
import re
import sqlite3
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
SRC_DB = ROOT / "data" / "aiscientist.db"
REPORTS_DIR = ROOT / "storage" / "reports"
IE_DIR = ROOT / "storage" / "iterative_experiments"
SHAXIANG_DATA = PROJECT_ROOT / "shaxiang-main" / "shaxiang-main" / "data"
SRC_SX_DB = SHAXIANG_DATA / "experiments.db"
CHARTS_DIR = SHAXIANG_DATA / "charts"
OUT_DIR = ROOT / "data" / "export_cloud"
OUT_DB = OUT_DIR / "aiscientist.db"
OUT_TAR = OUT_DIR / "reports_bundle.tar.gz"
OUT_IE_TAR = OUT_DIR / "iterative_experiments_bundle.tar.gz"
OUT_SX_TAR = OUT_DIR / "shaxiang_data_bundle.tar.gz"

PROJECT_IDS = [
    "6dbf4b5a-034b-4a63-a8bd-2c601588f477",  # 联邦康养（general）
    "93db5222-b1ee-48fc-8e16-7d4fed89ef2a",  # 人工智能取代医生
]


def _q_in(n: int) -> str:
    return ",".join("?" * n)


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _cols(con: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def copy_by_ids(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    table: str,
    id_col: str,
    ids: list[str],
) -> int:
    if not ids or not _table_exists(src, table):
        return 0
    cols = _cols(src, table)
    if id_col not in cols:
        return 0
    placeholders = _q_in(len(ids))
    rows = src.execute(
        f"SELECT * FROM {table} WHERE {id_col} IN ({placeholders})", ids
    ).fetchall()
    if not rows:
        return 0
    col_list = ",".join(f'"{c}"' for c in cols)
    qs = ",".join("?" * len(cols))
    dst.executemany(
        f'INSERT OR REPLACE INTO "{table}" ({col_list}) VALUES ({qs})',
        [tuple(r) for r in rows],
    )
    return len(rows)


def _ie_experiment_ids(pids: list[str]) -> list[str]:
    ids: list[str] = []
    for pid in pids:
        path = IE_DIR / f"{pid}.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("experiments") or data.get("items") or []
        else:
            items = []
        for e in items:
            if not isinstance(e, dict):
                continue
            eid = e.get("shaxiang_experiment_id") or e.get("id")
            if eid:
                ids.append(str(eid))
    return ids


def _chart_relpaths_from_db(con: sqlite3.Connection, experiment_ids: list[str]) -> set[str]:
    """从 iterations JSON 中收集 charts 相对路径（如 smoke/foo.png）。"""
    found: set[str] = set()
    if not experiment_ids:
        return found
    ph = _q_in(len(experiment_ids))
    rows = con.execute(
        f"SELECT result_json, analysis_json FROM iterations WHERE experiment_id IN ({ph})",
        experiment_ids,
    ).fetchall()
    for result_json, analysis_json in rows:
        for blob in (result_json, analysis_json):
            if not blob:
                continue
            for m in re.findall(r"iter_[A-Za-z0-9_\-]+\.png", blob):
                found.add(f"smoke/{m}")
    return found


def export_iterative_experiments(pids: list[str]) -> int:
    if OUT_IE_TAR.exists():
        OUT_IE_TAR.unlink()
    n = 0
    with tarfile.open(OUT_IE_TAR, "w:gz") as tar:
        for pid in pids:
            path = IE_DIR / f"{pid}.json"
            if path.is_file():
                tar.add(path, arcname=f"iterative_experiments/{pid}.json")
                n += 1
    return n


def export_shaxiang_subset(experiment_ids: list[str]) -> tuple[int, int]:
    """导出子集 experiments.db + 相关 charts。"""
    if OUT_SX_TAR.exists():
        OUT_SX_TAR.unlink()
    if not SRC_SX_DB.is_file():
        raise SystemExit(f"missing shaxiang db: {SRC_SX_DB}")

    subset_db = OUT_DIR / "_shaxiang_experiments.db"
    if subset_db.exists():
        subset_db.unlink()

    src = sqlite3.connect(SRC_SX_DB)
    dst = sqlite3.connect(subset_db)
    for row in src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        if row[0]:
            dst.execute(row[0])
    dst.commit()

    n_exp = 0
    n_iter = 0
    if experiment_ids:
        cols = _cols(src, "experiments")
        col_list = ",".join(f'"{c}"' for c in cols)
        qs = ",".join("?" * len(cols))
        ph = _q_in(len(experiment_ids))
        rows = src.execute(
            f"SELECT * FROM experiments WHERE id IN ({ph})", experiment_ids
        ).fetchall()
        dst.executemany(
            f'INSERT OR REPLACE INTO experiments ({col_list}) VALUES ({qs})',
            [tuple(r) for r in rows],
        )
        n_exp = len(rows)

        icols = _cols(src, "iterations")
        icol_list = ",".join(f'"{c}"' for c in icols)
        iqs = ",".join("?" * len(icols))
        irows = src.execute(
            f"SELECT * FROM iterations WHERE experiment_id IN ({ph})", experiment_ids
        ).fetchall()
        dst.executemany(
            f'INSERT OR REPLACE INTO iterations ({icol_list}) VALUES ({iqs})',
            [tuple(r) for r in irows],
        )
        n_iter = len(irows)

    chart_rels = _chart_relpaths_from_db(src, experiment_ids)
    dst.commit()
    dst.execute("VACUUM")
    dst.commit()
    src.close()
    dst.close()

    with tarfile.open(OUT_SX_TAR, "w:gz") as tar:
        tar.add(subset_db, arcname="experiments.db")
        for rel in sorted(chart_rels):
            path = CHARTS_DIR / rel
            if path.is_file():
                tar.add(path, arcname=f"charts/{rel.replace(chr(92), '/')}")
            else:
                alt = CHARTS_DIR / "smoke" / Path(rel).name
                if alt.is_file():
                    tar.add(alt, arcname=f"charts/smoke/{alt.name}")

    subset_db.unlink(missing_ok=True)
    return n_exp, n_iter


def main() -> None:
    if not SRC_DB.is_file():
        raise SystemExit(f"missing source db: {SRC_DB}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_DB.exists():
        OUT_DB.unlink()

    src = sqlite3.connect(SRC_DB)
    dst = sqlite3.connect(OUT_DB)
    # clone schema
    for row in src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        if row[0]:
            dst.execute(row[0])
    dst.commit()

    pids = PROJECT_IDS
    stats: dict[str, int] = {}
    stats["projects"] = copy_by_ids(src, dst, "projects", "id", pids)

    # documents -> chunks
    doc_ids = [
        r[0]
        for r in src.execute(
            f"SELECT id FROM documents WHERE project_id IN ({_q_in(len(pids))})", pids
        )
    ]
    stats["documents"] = copy_by_ids(src, dst, "documents", "id", doc_ids)
    stats["chunks"] = copy_by_ids(src, dst, "chunks", "document_id", doc_ids)

    # research artifacts
    for table, col in [
        ("hypotheses", "project_id"),
        ("experiment_designs", "project_id"),
        ("evidences", "project_id"),
        ("small_validations", "project_id"),
        ("datasets", "project_id"),
        ("multimodal_assets", "project_id"),
        ("pipeline_runs", "project_id"),
        ("reports", "project_id"),
        ("run_logs", "project_id"),
        ("project_prompt_overrides", "project_id"),
        ("coordinator_advice", "project_id"),
        ("proactive_contexts", "project_id"),
        ("research_projects", "id"),
    ]:
        if not _table_exists(src, table):
            continue
        if col not in _cols(src, table):
            continue
        stats[table] = copy_by_ids(src, dst, table, col, pids)

    # pipeline stage executions via run ids
    run_ids = [
        r[0]
        for r in src.execute(
            f"SELECT id FROM pipeline_runs WHERE project_id IN ({_q_in(len(pids))})",
            pids,
        )
    ]
    stats["pipeline_stage_executions"] = copy_by_ids(
        src, dst, "pipeline_stage_executions", "pipeline_run_id", run_ids
    )

    # report evaluations via report ids
    report_ids = [
        r[0]
        for r in src.execute(
            f"SELECT id FROM reports WHERE project_id IN ({_q_in(len(pids))})", pids
        )
    ]
    stats["report_evaluations"] = copy_by_ids(
        src, dst, "report_evaluations", "report_id", report_ids
    )

    # chat messages via session ids
    if _table_exists(src, "chat_sessions") and "project_id" in _cols(src, "chat_sessions"):
        sess_ids = [
            r[0]
            for r in src.execute(
                f"SELECT id FROM chat_sessions WHERE project_id IN ({_q_in(len(pids))})",
                pids,
            )
        ]
        stats["chat_sessions"] = copy_by_ids(src, dst, "chat_sessions", "id", sess_ids)
        if _table_exists(src, "chat_messages") and sess_ids:
            msg_col = "session_id" if "session_id" in _cols(src, "chat_messages") else None
            if msg_col:
                stats["chat_messages"] = copy_by_ids(
                    src, dst, "chat_messages", msg_col, sess_ids
                )

    # prompt_versions: keep all small reference rows if any, else skip
    if _table_exists(src, "prompt_versions"):
        n = copy_by_ids(
            src,
            dst,
            "prompt_versions",
            "id",
            [r[0] for r in src.execute("SELECT id FROM prompt_versions")],
        )
        stats["prompt_versions"] = n

    dst.commit()

    # report file ids
    file_ids = [
        r[0]
        for r in src.execute(
            f"SELECT pdf_path FROM reports WHERE project_id IN ({_q_in(len(pids))}) AND pdf_path IS NOT NULL",
            pids,
        )
    ]
    file_ids = [f for f in file_ids if f]

    if OUT_TAR.exists():
        OUT_TAR.unlink()
    with tarfile.open(OUT_TAR, "w:gz") as tar:
        for fid in file_ids:
            d = REPORTS_DIR / fid
            if d.is_dir():
                tar.add(d, arcname=f"reports/{fid}")

    dst.execute("VACUUM")
    dst.commit()
    src.close()
    dst.close()

    ie_n = export_iterative_experiments(pids)
    sx_ids = _ie_experiment_ids(pids)
    n_exp, n_iter = export_shaxiang_subset(sx_ids)
    stats["ie_json_files"] = ie_n
    stats["shaxiang_experiments"] = n_exp
    stats["shaxiang_iterations"] = n_iter

    print("export_ok")
    print("db_mb", round(OUT_DB.stat().st_size / 1024 / 1024, 2))
    print("tar_mb", round(OUT_TAR.stat().st_size / 1024 / 1024, 2))
    print("ie_tar_mb", round(OUT_IE_TAR.stat().st_size / 1024 / 1024, 2))
    print("sx_tar_mb", round(OUT_SX_TAR.stat().st_size / 1024 / 1024, 2))
    print("report_dirs", len(file_ids))
    print("sx_experiment_ids", sx_ids)
    for k, v in sorted(stats.items()):
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
