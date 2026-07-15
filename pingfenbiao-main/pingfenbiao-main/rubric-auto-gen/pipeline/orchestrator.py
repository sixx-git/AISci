"""
流水线编排模块 — 串联所有步骤，实现完整的评分表生成 + 评分 + 标注流程。

四种运行模式:
  1. generate    — 仅生成评分表 (task.json)
  2. score       — 基于已有评分表对报告打分
  3. highlight   — 基于已有评分表标注源 PDF
  4. full        — 完整流水线：生成 → 校准 → 评分 → 标注
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from common.auto_query import ensure_query
from .source_parser import SourceParser, SourceDocument
from .rubric_generator_v5 import RubricGenerator
from .calibrator import Calibrator
from .scorer import Scorer
from .highlighter import Highlighter

logger = logging.getLogger(__name__)


class Pipeline:
    """端到端流水线编排器。"""

    def __init__(self, config):
        self.config = config
        self.parser = SourceParser(verbose=config.verbose)
        self.generator = RubricGenerator(config)
        self.calibrator = Calibrator(config=config, verbose=config.verbose)
        self.scorer = Scorer(config)
        self.highlighter = Highlighter(config)

    # ── 公开接口 ─────────────────────────────────────────────────────

    def run_generate(self, source_dir: str, query: str,
                     output_dir: str, task_type: str = "literature_review") -> dict:
        """
        模式 1：仅生成评分表。

        Returns:
            task.json 内容
        """
        self._setup_logging()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 解析源文件
        logger.info("=" * 60)
        logger.info("Step 1/3: 解析源文件")
        logger.info("=" * 60)
        sources = self.parser.parse_directory(source_dir)
        if not sources:
            raise ValueError(f"在 {source_dir} 中未找到可解析的文件")

        query = ensure_query(query, sources, task_type, self.config)

        # 生成评分表
        logger.info("")
        logger.info("=" * 60)
        logger.info("Step 2/3: 生成评分表")
        logger.info("=" * 60)
        self.config.task_type = task_type
        self.config.query = query
        task_output = self.generator.generate(sources, query, task_type)

        # 校准
        logger.info("")
        logger.info("=" * 60)
        logger.info("Step 3/3: 校准评分表")
        logger.info("=" * 60)
        task_output = self.calibrator.calibrate(task_output)

        # 保存
        task_path = output_path / "task.json"
        task_path.write_text(
            json.dumps(task_output, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        logger.info(f"\n评分表已保存到: {task_path}")
        self._print_summary(task_output)

        return task_output

    def run_score(self, task_json_path: str, report_path: str,
                  output_dir: str, source_dir: str = "") -> dict:
        """
        模式 2：基于已有评分表对报告打分。

        Returns:
            rubric_scores.json 内容
        """
        self._setup_logging()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 加载评分表
        with open(task_json_path, "r", encoding="utf-8") as f:
            rubric_data = json.load(f)

        logger.info("=" * 60)
        logger.info("评分模式: 对报告进行自动评分")
        logger.info("=" * 60)
        logger.info(f"评分表: {task_json_path}")
        logger.info(f"报告: {report_path}")

        sources = None
        if source_dir:
            sources = self.parser.parse_directory(source_dir)
            logger.info(f"源文献上下文: {len(sources)} 个文件")

        scores = self.scorer.score(
            report_path,
            rubric_data,
            sources=sources,
            output_dir=output_dir,
        )

        # 保存
        scores_path = output_path / "self_check"
        scores_path.mkdir(parents=True, exist_ok=True)
        scores_file = scores_path / "rubric_scores.json"
        scores_file.write_text(
            json.dumps(scores, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        logger.info(f"\n评分结果已保存到: {scores_file}")
        self._print_scores(scores)

        return scores

    def run_highlight(self, task_json_path: str, source_dir: str,
                      output_dir: str) -> None:
        """
        模式 3：基于已有评分表标注源 PDF。
        """
        self._setup_logging()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with open(task_json_path, "r", encoding="utf-8") as f:
            rubric_data = json.load(f)

        sources = self.parser.parse_directory(source_dir)

        logger.info("=" * 60)
        logger.info("标注模式: 在源 PDF 上标注关键段落")
        logger.info("=" * 60)

        self.highlighter.process_sources(sources, rubric_data, output_dir)
        logger.info(f"\n标注完成，输出目录: {output_path / 'sources'}")

    def run_full(self, source_dir: str, query: str, report_path: str,
                 output_dir: str, task_type: str = "literature_review") -> dict:
        """
        模式 4：完整流水线。

        Returns:
            {"task": task_output, "scores": scores_output}
        """
        start_time = time.time()
        self._setup_logging()

        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║         评分表自动生成 + 评分 完整流水线                ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")

        # Step 1: 生成评分表
        task_output = self.run_generate(source_dir, query, output_dir, task_type)

        # Step 2: 评分
        logger.info("")
        logger.info("=" * 60)
        logger.info("Step 4: 对报告进行自动评分")
        logger.info("=" * 60)
        task_json_path = str(Path(output_dir) / "task.json")
        sources = self.parser.parse_directory(source_dir)
        scores = self.scorer.score(
            report_path,
            task_output,
            sources=sources,
            output_dir=output_dir,
        )

        scores_dir = Path(output_dir) / "self_check"
        scores_dir.mkdir(parents=True, exist_ok=True)
        scores_file = scores_dir / "rubric_scores.json"
        scores_file.write_text(
            json.dumps(scores, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        self._print_scores(scores)

        # Step 3: PDF 高亮标注
        logger.info("")
        logger.info("=" * 60)
        logger.info("Step 5: 标注源 PDF 关键段落")
        logger.info("=" * 60)
        sources = self.parser.parse_directory(source_dir)
        self.highlighter.process_sources(sources, task_output, output_dir)

        elapsed = time.time() - start_time
        logger.info(f"\n{'=' * 60}")
        logger.info(f"完整流水线执行完毕，耗时 {elapsed:.1f} 秒")
        logger.info(f"输出目录: {output_dir}")
        logger.info(f"{'=' * 60}")

        return {"task": task_output, "scores": scores}

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _setup_logging(self):
        """配置日志输出。"""
        if self.config.verbose:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                handlers=[logging.StreamHandler()],
            )

    def _print_summary(self, task_output: dict):
        """打印评分表摘要。"""
        rubrics = task_output.get("rubrics", {})
        dims = rubrics.get("dimensions", [])
        total = rubrics.get("total_score", 0)
        meta = task_output.get("generation_meta", {})
        stats = meta.get("dimension_stats", {})

        logger.info(f"\n{'─' * 50}")
        logger.info(f"评分表摘要 v{meta.get('version', '1.0')}")
        logger.info(f"{'─' * 50}")
        logger.info(f"总分: {total} 分")
        logger.info(f"维度数: {len(dims)}")

        for dim in dims:
            dim_id = dim["dimension_id"]
            items = dim.get("items", [])
            critical = sum(1 for it in items if it.get("role") == "Critical")
            mandatory = sum(1 for it in items if it.get("role") == "Mandatory")
            standard = sum(1 for it in items if it.get("role") == "Standard")
            s = stats.get(dim_id, {})
            linked = s.get("source_linked_ratio", 0)
            logger.info(
                f"  {dim['dimension_name']}: {dim['max_score']}分, "
                f"{len(items)}项 "
                f"(C={critical}, M={mandatory}, S={standard}, src={linked:.0%})"
            )

        calibration = task_output.get("calibration", {})
        if calibration.get("issues_found", 0) > 0:
            logger.info(f"\n校准发现 {calibration['issues_found']} 个问题")
            for issue in calibration.get("issues", [])[:5]:
                logger.info(f"  ⚠ {issue}")
        fixes = calibration.get("fixes_applied", [])
        if fixes:
            logger.info(f"  ✓ 自动修复 {len(fixes)} 项")

    def _print_scores(self, scores: dict):
        """打印评分结果摘要。"""
        logger.info(f"\n{'─' * 50}")
        logger.info(f"评分结果")
        logger.info(f"{'─' * 50}")
        logger.info(
            f"总分: {scores['raw_score']}/{scores['total_score']} "
            f"({scores['score_percentage']}%)"
        )

        for dim in scores.get("dimension_scores", []):
            pct = dim["score"] / dim["max_score"] * 100 if dim["max_score"] > 0 else 0
            logger.info(f"  {dim['dimension_id']}: {dim['score']}/{dim['max_score']} ({pct:.1f}%)")

        meta = scores.get("scoring_meta", {})
        zero_count = meta.get(
            "zero_count",
            sum(1 for it in scores.get("items", []) if it.get("score", 0) == 0),
        )
        full_count = meta.get("full_mark_count", 0)
        retried = meta.get("retried_items", [])
        logger.info(f"\n  零分项: {zero_count}, 满分项: {full_count}")
        if retried:
            logger.info(f"  补评项: {len(retried)}")
        warns = meta.get("warnings", [])
        if warns:
            logger.info(f"  告警: {len(warns)} 条（详见 scoring_meta.warnings）")
