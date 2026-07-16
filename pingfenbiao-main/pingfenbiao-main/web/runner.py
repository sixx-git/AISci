"""调用三套 rubric 生成器 + 影响力评估的统一入口。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PACKAGES = {
    "claim_verification": {
        "dir": ROOT / "rubric-auto-gen",
        "label": "主张核查",
        "extra_args": ["--task-type", "claim_verification"],
    },
    "data_analysis": {
        "dir": ROOT / "rubric-auto-gen-2",
        "label": "数据分析",
        "extra_args": [],
    },
    "literature_review": {
        "dir": ROOT / "rubric-auto-gen-3",
        "label": "科学调研",
        "extra_args": [],
    },
}

# 影响力预测不依赖 task_type，但需要兼容界面
IMPACT_LABEL = "科学影响力预测"


ALLOWED_SUFFIXES = {".pdf", ".csv", ".md", ".txt"}
REPORT_SUFFIXES = {".md", ".txt", ".pdf"}


def resolve_task_type(task_json: dict) -> str:
    """从 task.json 推断应使用的生成器包。"""
    task_type = (task_json.get("task_type") or "").strip()
    if task_type in PACKAGES:
        return task_type
    raise ValueError(
        f"task.json 中未知的 task_type: {task_type!r} "
        f"（支持 claim_verification / data_analysis / literature_review）"
    )


def scores_output_path(task_type: str, output_dir: Path) -> Path:
    """各生成器 score 命令的输出路径。"""
    if task_type == "claim_verification":
        return output_dir / "self_check" / "rubric_scores.json"
    return output_dir / "rubric_scores.json"


def _apply_api_key(cmd: list[str], env: dict[str, str], api_key: str) -> None:
    if api_key:
        cmd.extend(["--api-key", api_key])
        env["DASHSCOPE_API_KEY"] = api_key


def build_generate_command(
    task_type: str,
    query: str,
    source_dir: Path,
    output_dir: Path,
    api_key: str = "",
    *,
    quiet: bool = True,
) -> tuple[list[str], dict[str, str]]:
    if task_type not in PACKAGES:
        raise ValueError(f"未知任务类型: {task_type}")

    pkg = PACKAGES[task_type]
    main_py = pkg["dir"] / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"未找到生成器: {main_py}")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(main_py),
        "generate",
        "--source-dir",
        str(source_dir),
        "--query",
        query.strip(),
        "--output",
        str(output_dir),
        *pkg["extra_args"],
    ]
    if quiet:
        cmd.append("--quiet")

    env = os.environ.copy()
    _apply_api_key(cmd, env, api_key)

    return cmd, env


def build_score_command(
    task_type: str,
    task_path: Path,
    report_path: Path,
    output_dir: Path,
    source_dir: Path | None = None,
    api_key: str = "",
    *,
    max_report_chars: int = 0,
    quiet: bool = True,
) -> tuple[list[str], dict[str, str]]:
    if task_type not in PACKAGES:
        raise ValueError(f"未知任务类型: {task_type}")

    pkg = PACKAGES[task_type]
    main_py = pkg["dir"] / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"未找到生成器: {main_py}")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(main_py),
        "score",
        "--task",
        str(task_path),
        "--report",
        str(report_path),
        "--output",
        str(output_dir),
    ]
    if source_dir and source_dir.exists() and any(source_dir.iterdir()):
        cmd.extend(["--source-dir", str(source_dir)])
    if max_report_chars > 0:
        cmd.extend(["--max-report-chars", str(max_report_chars)])
    if quiet:
        cmd.append("--quiet")

    env = os.environ.copy()
    _apply_api_key(cmd, env, api_key)

    return cmd, env
