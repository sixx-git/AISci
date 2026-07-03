"""压缩 SQLite 中膨胀的 pipeline JSON，并 VACUUM。"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import init_db, SessionLocal
from app.models.pipeline import PipelineRun, PipelineStageExecution
from app.services.data_finder_slim import slim_results_for_checkpoint, slim_stage_input


def main() -> int:
    init_db()
    from app.core.database import SessionLocal as SL

    db = SL()
    slimmed_stages = 0
    slimmed_runs = 0

    for stage in db.query(PipelineStageExecution).all():
        raw = stage.input_data
        if not raw:
            continue
        try:
            blob = json.dumps(raw, ensure_ascii=False)
        except (TypeError, ValueError):
            continue
        if len(blob) < 200_000:
            continue
        stage.input_data = slim_stage_input(raw if isinstance(raw, dict) else {})
        slimmed_stages += 1

    for run in db.query(PipelineRun).all():
        meta = run.extra_metadata if isinstance(run.extra_metadata, dict) else None
        if not meta:
            continue
        try:
            blob = json.dumps(meta, ensure_ascii=False)
        except (TypeError, ValueError):
            continue
        if len(blob) < 200_000:
            continue
        cp = meta.get("pipeline_checkpoint")
        if isinstance(cp, dict) and isinstance(cp.get("results"), dict):
            cp = dict(cp)
            cp["results"] = slim_results_for_checkpoint(cp["results"])
            meta["pipeline_checkpoint"] = cp
        run.extra_metadata = meta
        flag_modified(run, "extra_metadata")
        slimmed_runs += 1

    db.commit()
    db.close()

    from app.core.config import get_settings

    db_path = get_settings().DATABASE_URL.replace("sqlite:///", "")
    size_before = os.path.getsize(db_path) / 1024 / 1024

    import sqlite3

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("VACUUM")
    conn.close()

    size_after = os.path.getsize(db_path) / 1024 / 1024
    print(f"slimmed stages: {slimmed_stages}, runs: {slimmed_runs}")
    print(f"db size: {size_before:.1f} MB -> {size_after:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
