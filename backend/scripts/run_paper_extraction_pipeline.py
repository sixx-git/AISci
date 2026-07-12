"""从已入库论文抽表抽图、对齐合并为分析库（独立工具，不参与 Pipeline）。

用法:
  python scripts/run_paper_extraction_pipeline.py <project_id>
  python scripts/run_paper_extraction_pipeline.py <project_id> --question "研究问题"
  python scripts/run_paper_extraction_pipeline.py <project_id> --gap-search
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db
from app.services.data_finder_service import get_data_finder_service


async def _run(
    project_id: str,
    research_question: str,
    *,
    auto_import: bool,
    enable_gap_search: bool,
) -> dict:
    init_db()
    from app.core.database import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("数据库未初始化")
    db = SessionLocal()
    try:
        svc = get_data_finder_service(db)
        return await svc.run_paper_extraction_pipeline(
            project_id=project_id,
            research_question=research_question,
            auto_import=auto_import,
            enable_gap_search=enable_gap_search,
        )
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="论文抽表抽图 + 合并建库（独立工具）")
    parser.add_argument("project_id")
    parser.add_argument("--question", default="", help="研究问题（可选，默认读项目）")
    parser.add_argument("--no-auto-import", action="store_true", help="不自动 import HF/Zenodo 样例")
    parser.add_argument("--gap-search", action="store_true", help="启用 Gap 多轮补搜")
    args = parser.parse_args()

    rq = args.question.strip()
    if not rq:
        init_db()
        from app.core.database import SessionLocal

        if SessionLocal is None:
            raise RuntimeError("数据库未初始化")
        db = SessionLocal()
        try:
            from app.services.project_service import ProjectService

            p = ProjectService(db).get_project(args.project_id)
            rq = (getattr(p, "research_question", None) or "") if p else ""
        finally:
            db.close()

    result = asyncio.run(_run(
        args.project_id,
        rq,
        auto_import=not args.no_auto_import,
        enable_gap_search=args.gap_search,
    ))
    stats = (result.get("data_acquisition") or {}).get("stats") or {}
    gate = result.get("release_gate") or {}
    print("mode:", (result.get("data_acquisition") or {}).get("mode"))
    print("tables:", stats.get("tables"))
    print("merged_rows:", stats.get("merged_rows"))
    print("release_gate_passed:", gate.get("passed"))
    print(json.dumps({
        "external_candidates": stats.get("external_candidates"),
        "gap_rounds": stats.get("gap_rounds"),
        "total_duration_ms": stats.get("total_duration_ms"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
