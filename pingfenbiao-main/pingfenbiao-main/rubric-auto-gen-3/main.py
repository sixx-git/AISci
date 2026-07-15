#!/usr/bin/env python3
"""
科学调研报告评分表生成器 — CLI 入口

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

from common.auto_query import ensure_query
from common.scorer import add_scoring_arguments, apply_scoring_options
from config import Config
from pipeline.source_parser import SourceParser
from pipeline.rubric_generator import RubricGenerator
from pipeline.scorer import Scorer
from pipeline.highlighter import Highlighter


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="科学调研报告评分表生成器 — Rubric Auto-Gen v3 (Literature Review)",
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


def run_generate(config, source_dir, query, output_dir):
    """生成评分表。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 解析源文件
    parser = SourceParser(verbose=config.verbose)
    sources = parser.parse_directory(source_dir)
    if not sources:
        raise ValueError(f"源文件目录中没有可解析的文件: {source_dir}")

    query = ensure_query(query, sources, config.task_type, config)

    # 生成评分表
    generator = RubricGenerator(config)
    result = generator.generate(sources, query)

    # 保存
    task_path = output_path / "task.json"
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 评分表已生成: {task_path}")

    return result


def run_score(
    config,
    task_json_path,
    report_path,
    output_dir,
    source_dir: str = "",
):
    """对报告评分。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 加载 task.json
    with open(task_json_path, "r", encoding="utf-8") as f:
        rubric_data = json.load(f)

    sources = None
    if source_dir:
        parser = SourceParser(verbose=config.verbose)
        sources = parser.parse_directory(source_dir)

    # 评分
    scorer = Scorer(config)
    result = scorer.score(
        report_path,
        rubric_data,
        sources=sources,
        output_dir=output_dir,
    )

    # 保存
    scores_path = output_path / "rubric_scores.json"
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    pct = result.get("score_percentage", 0)
    print(f"\n[OK] 评分完成: {result['raw_score']}/{result['total_score']} ({pct}%)")
    print(f"     评分结果: {scores_path}")

    return result


def run_highlight(config, task_json_path, source_dir, output_dir):
    """标注源 PDF。"""
    # 加载 task.json
    with open(task_json_path, "r", encoding="utf-8") as f:
        rubric_data = json.load(f)

    # 解析源文件
    parser = SourceParser(verbose=config.verbose)
    sources = parser.parse_directory(source_dir)

    # 标注
    highlighter = Highlighter(config)
    highlighter.process_sources(sources, rubric_data, output_dir)

    sources_path = Path(output_dir) / "sources"
    print(f"\n[OK] 标注完成: {sources_path}")


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 配置日志
    logging.basicConfig(
        level=logging.WARNING if getattr(args, "quiet", False) else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 构建配置
    config = build_config(args)
    apply_scoring_options(config, args)

    try:
        if args.command == "generate":
            result = run_generate(
                config, args.source_dir, args.query, args.output,
            )

        elif args.command == "score":
            run_score(
                config,
                args.task,
                args.report,
                args.output,
                source_dir=getattr(args, "source_dir", "") or "",
            )

        elif args.command == "highlight":
            run_highlight(
                config, args.task, args.source_dir, args.output,
            )

        elif args.command == "full":
            output_dir = args.output
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # 生成评分表
            print("=" * 60)
            print("Step 1: 生成评分表")
            print("=" * 60)
            result = run_generate(
                config, args.source_dir, args.query, output_dir,
            )

            # 评分
            print("\n" + "=" * 60)
            print("Step 2: 对报告评分")
            print("=" * 60)
            task_path = output_path / "task.json"
            score_result = run_score(
                config,
                str(task_path),
                args.report,
                output_dir,
                source_dir=args.source_dir,
            )

            # 标注
            print("\n" + "=" * 60)
            print("Step 3: 标注源 PDF")
            print("=" * 60)
            run_highlight(
                config, str(task_path), args.source_dir, output_dir,
            )

            print("\n" + "=" * 60)
            pct = score_result.get("score_percentage", 0)
            print(f"[OK] 完整流水线执行完毕")
            print(f"     评分表: {task_path}")
            print(f"     评分: {score_result['raw_score']}/{score_result['total_score']} ({pct}%)")
            print(f"     标注: {output_path / 'sources'}")
            print("=" * 60)

    except ValueError as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        logging.exception("详细错误信息:")
        sys.exit(1)


if __name__ == "__main__":
    main()
