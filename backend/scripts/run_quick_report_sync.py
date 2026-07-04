"""同步执行一键报告（不依赖 uvicorn 后台线程，适合试运行/调试）。"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db
from app.schemas.project import QuickReportRequest
from app.services.pipeline_service import get_pipeline_service
from app.services.quick_report_service import get_quick_report_service


def main() -> int:
    parser = argparse.ArgumentParser(description="同步运行一键报告")
    parser.add_argument("--question-name", required=True)
    parser.add_argument("--file-description", required=True)
    parser.add_argument("--project-id", default="", help="已有项目 ID（可选，跳过创建）")
    parser.add_argument("--run-id", default="", help="已有 run_id，从该 run 续跑")
    args = parser.parse_args()

    init_db()
    from app.core.database import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("数据库未初始化")
    db = SessionLocal()
    try:
        if args.run_id:
            run_id = args.run_id.strip()
            print(f"=== 续跑 run_id={run_id} ===", flush=True)
        else:
            body = QuickReportRequest(
                question_name=args.question_name,
                file_description=args.file_description,
            )
            result = get_quick_report_service(db).start(body)
            run_id = result["run_id"]
            print("=== 一键报告已创建 ===", flush=True)
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

        svc = get_pipeline_service(db)
        print(f"=== 开始同步执行 Pipeline run_id={run_id} ===", flush=True)
        svc.execute_pipeline_run(run_id)
        run = svc.db_pipeline_run
        status = run.status.value if run and hasattr(run.status, "value") else str(run.status if run else "?")
        print("=== 完成 ===", flush=True)
        print("status:", status, flush=True)
        print("report_id:", run.final_report_id if run else None, flush=True)
        print("error:", run.error_message if run else None, flush=True)
        print("failed_stage:", run.failed_stage if run else None, flush=True)
        return 0 if status.lower() == "completed" else 1
    except Exception as exc:
        print("FAILED:", exc, file=sys.stderr, flush=True)
        import traceback

        traceback.print_exc()
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
