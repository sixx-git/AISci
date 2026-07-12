"""轻量多源数据发现（跳过图表/VLM），用于领域修复后快速重采。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db
from app.services.data_finder_service import get_data_finder_service


async def _run(project_id: str, research_question: str) -> dict:
    init_db()
    from app.core.database import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("数据库未初始化")
    db = SessionLocal()
    try:
        svc = get_data_finder_service(db)
        return await svc.run_dataset_discovery(
            project_id=project_id,
            research_question=research_question,
        )
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_id")
    parser.add_argument("--question", default="", help="研究问题（可选，默认读项目）")
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

    result = asyncio.run(_run(args.project_id, rq))
    ext = result.get("external_candidates") or []
    print("external_candidates:", len(ext))
    for c in ext[:10]:
        print(
            "-",
            c.get("source_platform"),
            "|",
            (c.get("dataset_name") or "")[:70],
            "| score=",
            c.get("relevance_score"),
        )
    geo = [c for c in ext if "geo" in str(c.get("source_platform", "")).lower()]
    print("NCBI GEO count:", len(geo))
    print(json.dumps({"count": len(ext), "warnings": result.get("warnings", [])[:5]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
