"""上传数据后同步续跑一键报告（不依赖 uvicorn --reload）。"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db, SessionLocal
from app.services.pipeline_service import get_pipeline_service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", help="Pipeline run_id")
    args = parser.parse_args()

    init_db()
    from app.core.database import SessionLocal as SL
    if SL is None:
        raise RuntimeError("数据库未初始化")
    db = SL()
    try:
        svc = get_pipeline_service(db)
        print("=== resume_after_data_upload ===")
        info = svc.resume_after_data_upload(args.run_id)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print("=== execute_pipeline_run (sync) ===")
        svc.execute_pipeline_run(args.run_id)
        run = svc.db_pipeline_run
        print("final status:", run.status if run else "?")
        print("report_id:", run.final_report_id if run else None)
        print("error:", run.error_message if run else None)
        return 0 if run and str(run.status).lower() in ("completed", "COMPLETED") else 1
    except Exception as exc:
        print("FAILED:", exc, file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
