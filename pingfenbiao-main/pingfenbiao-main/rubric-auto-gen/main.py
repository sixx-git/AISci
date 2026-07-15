#!/usr/bin/env python3
"""
Rubric Auto-Generator — CLI 入口

用法:
  # 1. 仅生成评分表
  python main.py generate --source-dir ./papers --query "研究问题..." --output ./output

  # 2. 对报告评分（需要已有的 task.json）
  python main.py score --task ./output/task.json --report ./report.md --output ./output

  # 3. 标注源 PDF
  python main.py highlight --task ./output/task.json --source-dir ./papers --output ./output

  # 4. 完整流水线
  python main.py full --source-dir ./papers --query "研究问题..." --report ./report.md --output ./output

环境变量:
  DASHSCOPE_API_KEY  — 阿里云 DashScope API Key（必填）
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 将项目根目录加入 path
_PKG = Path(__file__).parent
_ROOT = _PKG.parent
sys.path.insert(0, str(_PKG))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import Config
from pipeline.orchestrator import Pipeline
from common.scorer import add_scoring_arguments, apply_scoring_options


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="评分表自动生成流水线 — Rubric Auto-Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="运行模式")

    # ── generate ──
    gen_parser = subparsers.add_parser("generate", help="仅生成评分表")
    gen_parser.add_argument("--source-dir", required=True, help="源文件目录 (PDF/CSV/MD)")
    gen_parser.add_argument("--query", default="", help="研究问题/任务描述（可选，留空则从文献自动生成）")
    gen_parser.add_argument("--output", default="./output", help="输出目录")
    gen_parser.add_argument("--task-type", default="claim_verification",
                           choices=["literature_review", "claim_verification", "data_analysis"],
                           help="任务类型")
    gen_parser.add_argument("--task-id", default="", help="任务 ID")
    gen_parser.add_argument("--subject", default="", help="学科领域")

    # ── score ──
    score_parser = subparsers.add_parser("score", help="对报告自动评分")
    score_parser.add_argument("--task", required=True, help="task.json 路径")
    score_parser.add_argument("--report", required=True, help="待评报告路径")
    score_parser.add_argument("--output", default="./output", help="输出目录")
    add_scoring_arguments(score_parser)

    # ── highlight ──
    hl_parser = subparsers.add_parser("highlight", help="标注源 PDF")
    hl_parser.add_argument("--task", required=True, help="task.json 路径")
    hl_parser.add_argument("--source-dir", required=True, help="源文件目录")
    hl_parser.add_argument("--output", default="./output", help="输出目录")

    # ── full ──
    full_parser = subparsers.add_parser("full", help="完整流水线")
    full_parser.add_argument("--source-dir", required=True, help="源文件目录")
    full_parser.add_argument("--query", default="", help="研究问题/任务描述（可选，留空则从文献自动生成）")
    full_parser.add_argument("--report", required=True, help="待评报告路径")
    full_parser.add_argument("--output", default="./output", help="输出目录")
    full_parser.add_argument("--task-type", default="claim_verification",
                            choices=["literature_review", "claim_verification", "data_analysis"],
                            help="任务类型")
    full_parser.add_argument("--task-id", default="", help="任务 ID")
    full_parser.add_argument("--subject", default="", help="学科领域")
    add_scoring_arguments(full_parser, include_source_dir=False)

    # 通用参数
    for sub in [gen_parser, score_parser, hl_parser, full_parser]:
        sub.add_argument("--api-key", default="", help="DashScope API Key (或设环境变量)")
        sub.add_argument("--rubric-model", default="", help="评分表生成模型")
        sub.add_argument("--scoring-model", default="", help="评分模型")
        sub.add_argument("--quiet", action="store_true", help="安静模式")

    return parser


def build_config(args) -> Config:
    """从 CLI 参数构建 Config。"""
    kwargs = {"api_key": args.api_key}
    if hasattr(args, "task_type"):
        kwargs["task_type"] = args.task_type
    if hasattr(args, "task_id") and args.task_id:
        kwargs["task_id"] = args.task_id
    if hasattr(args, "subject") and args.subject:
        kwargs["subject"] = args.subject
    if hasattr(args, "query"):
        kwargs["query"] = args.query
    if args.rubric_model:
        kwargs["rubric_model"] = args.rubric_model
    if args.scoring_model:
        kwargs["scoring_model"] = args.scoring_model
    if args.quiet:
        kwargs["verbose"] = False

    return Config(**kwargs)


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 构建配置
    config = build_config(args)
    apply_scoring_options(config, args)

    # 创建流水线
    pipeline = Pipeline(config)

    try:
        if args.command == "generate":
            result = pipeline.run_generate(
                source_dir=args.source_dir,
                query=args.query,
                output_dir=args.output,
                task_type=args.task_type,
            )
            print(f"\n[OK] 评分表已生成: {Path(args.output) / 'task.json'}")

        elif args.command == "score":
            result = pipeline.run_score(
                task_json_path=args.task,
                report_path=args.report,
                output_dir=args.output,
                source_dir=getattr(args, "source_dir", "") or "",
            )
            pct = result.get("score_percentage", 0)
            print(f"\n[OK] 评分完成: {result['raw_score']}/{result['total_score']} ({pct}%)")

        elif args.command == "highlight":
            pipeline.run_highlight(
                task_json_path=args.task,
                source_dir=args.source_dir,
                output_dir=args.output,
            )
            print(f"\n[OK] 标注完成: {Path(args.output) / 'sources'}")

        elif args.command == "full":
            result = pipeline.run_full(
                source_dir=args.source_dir,
                query=args.query,
                report_path=args.report,
                output_dir=args.output,
                task_type=args.task_type,
            )
            pct = result["scores"].get("score_percentage", 0)
            print(f"\n[OK] 完整流水线执行完毕")
            print(f"  评分表: {Path(args.output) / 'task.json'}")
            print(f"  评分: {result['scores']['raw_score']}/{result['scores']['total_score']} ({pct}%)")
            print(f"  标注: {Path(args.output) / 'sources'}")

    except ValueError as e:
        print(f"\n✗ 错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 异常: {e}", file=sys.stderr)
        logging.exception("详细错误信息:")
        sys.exit(1)


if __name__ == "__main__":
    main()
