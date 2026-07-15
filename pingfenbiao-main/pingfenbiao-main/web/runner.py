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

TASK_TYPE_TO_PACKAGE = {
    "claim_verification": "claim_verification",
    "data_analysis": "data_analysis",
    "literature_review": "literature_review",
}


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


def generate_rubric(
    task_type: str,
    query: str,
    source_dir: Path,
    output_dir: Path,
    api_key: str = "",
) -> dict:
    pkg = PACKAGES[task_type]
    cmd, env = build_generate_command(
        task_type, query, source_dir, output_dir, api_key, quiet=True
    )

    proc = subprocess.run(
        cmd,
        cwd=str(pkg["dir"]),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "生成失败").strip()
        raise RuntimeError(err[-2000:])

    task_path = output_dir / "task.json"
    if not task_path.exists():
        raise FileNotFoundError("生成完成但未找到 task.json")

    return json.loads(task_path.read_text(encoding="utf-8"))


def run_impact_prediction(
    source_dir: Path,
    output_dir: Path,
    api_key: str = "",
) -> dict:
    """运行科学影响力预测（纯 Python 调用，不依赖子进程）。

    流程：
    1. 从上传的 PDF 文件中提取 DOI/标题
    2. 通过 OpenAlex API 获取元数据
    3. 调用 LLM 评估影响力（30 分）
    4. 计算组合评级

    Returns:
        包含 metadata、impact、rating 的完整结果字典。
    """
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from common.doi_extractor import extract_doi, extract_title
    from common.metadata_fetcher import fetch_work_by_doi, fetch_work_by_title
    from common.impact_evaluator import evaluate_impact
    from common.composite_scorer import calculate_composite_rating

    output_dir.mkdir(parents=True, exist_ok=True)

    # 找到第一个 PDF 文件
    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError("未找到 PDF 文件，影响力预测需要上传论文 PDF")

    pdf_path = pdf_files[0]

    # Step 1: 提取 DOI/标题
    doi = extract_doi(pdf_path)
    title = extract_title(pdf_path)

    result = {
        "pdf_file": pdf_path.name,
        "doi": doi,
        "title": title,
    }

    # Step 2: 获取元数据
    metadata = None
    if doi:
        metadata = fetch_work_by_doi(doi)
    if not metadata and title:
        metadata = fetch_work_by_title(title)

    result["metadata"] = metadata

    if not metadata:
        result["error"] = "无法获取论文元数据（DOI 提取失败且标题匹配失败）"
        result["impact"] = None
        result["rating"] = calculate_composite_rating(
            content_score_pct=None,
            impact_score=None,
            task_type="impact_only",
        )
        return result

    # Step 3: LLM 影响力评估
    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 使用 api_key 参数或从环境变量读取
    effective_api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not effective_api_key:
        # 尝试从 .env 文件读取
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY="):
                    effective_api_key = line.split("=", 1)[1].strip().strip("'\"")
                    break

    if not effective_api_key:
        raise ValueError("未找到 DASHSCOPE_API_KEY，影响力评估需要 LLM 调用")

    from openai import OpenAI
    client = OpenAI(api_key=effective_api_key, base_url=DASHSCOPE_BASE_URL, timeout=120)

    impact = evaluate_impact(metadata, client)
    result["impact"] = impact

    # Step 4: 组合评级
    impact_score = impact.get("total_score") if impact else None
    rating = calculate_composite_rating(
        content_score_pct=None,
        impact_score=impact_score,
        task_type="impact_only",
    )
    result["rating"] = rating

    # 保存结果
    output_path = output_dir / "impact_report.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return result
