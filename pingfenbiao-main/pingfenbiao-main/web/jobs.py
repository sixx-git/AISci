"""Web 端异步生成/评分/影响力预测任务与状态管理。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runner import (
    PACKAGES,
    IMPACT_LABEL,
    build_generate_command,
    build_score_command,
    scores_output_path,
)

MAX_LOG_LINES = 40

GENERATE_STAGE_RULES: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"No query provided|generating from source", re.I), 5, "正在从文献自动生成研究问题…"),
    (re.compile(r"Auto-generated query|Using default query fallback", re.I), 12, "研究问题已就绪"),
    (re.compile(r"Step 1/3|解析源文件|parse_directory", re.I), 15, "解析上传的文献…"),
    (re.compile(r"\[Stage 1a\]|Parsing query sub", re.I), 20, "解析研究问题子项…"),
    (re.compile(r"\[Stage 1b\]|Extracting key", re.I), 30, "从文献提取要点…"),
    (re.compile(r"\[Stage 1c\]|Generalizing", re.I), 40, "概念泛化与术语过滤…"),
    (re.compile(r"\[Stage 2\]|Generating rubric", re.I), 55, "生成评分项（LLM，通常最耗时）…"),
    (re.compile(r"\[Stage 3a\]|calibration", re.I), 72, "规则校准…"),
    (re.compile(r"\[Stage 3b\]|deduplication", re.I), 85, "LLM 去重…"),
    (re.compile(r"\[Stage 3c\]|Claim verification|quality policy", re.I), 92, "质量策略后处理…"),
    (re.compile(r"Generation Complete|Rubric Generation Complete", re.I), 98, "生成完成，正在保存…"),
]

SCORE_BATCH_RE = re.compile(r"Evaluating batch (\d+)/(\d+)", re.I)

SCORE_STAGE_RULES: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"评分模式|对报告进行自动评分", re.I), 8, "加载评分表与报告…"),
    (re.compile(r"报告长度|共 \d+ 条评分项", re.I), 12, "解析报告，准备逐条评分…"),
    (re.compile(r"源文献上下文", re.I), 15, "已加载源文献上下文…"),
    (re.compile(r"报告已截断", re.I), 16, "长报告已智能截断…"),
    (re.compile(r"补评漏项", re.I), 70, "补评遗漏项…"),
    (re.compile(r"评分结果已保存|评分完成|\[OK\] 评分完成", re.I), 98, "评分完成，正在保存…"),
]

_LOG_PREFIX = re.compile(r"^\d{2}:\d{2}:\d{2}\s+\[(\w+)\]\s+\S+:\s*")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_log_line(line: str) -> str:
    line = line.rstrip("\r\n")
    return _LOG_PREFIX.sub("", line).strip()


def _progress_from_line(
    line: str,
    current: int,
    job_mode: str,
) -> tuple[int, str | None]:
    rules = GENERATE_STAGE_RULES if job_mode == "generate" else SCORE_STAGE_RULES
    for pattern, pct, msg in rules:
        if pattern.search(line):
            return max(current, pct), msg

    if job_mode == "score":
        m = SCORE_BATCH_RE.search(line)
        if m:
            batch_num, total = int(m.group(1)), max(int(m.group(2)), 1)
            pct = 15 + int(batch_num / total * 75)
            return max(current, pct), f"正在评分 batch {batch_num}/{total}…"

    return current, None


class JobManager:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}

    def _status_path(self, job_id: str) -> Path:
        return self.work_dir / job_id / "status.json"

    def _write_status(self, job_id: str, data: dict[str, Any]) -> None:
        path = self._status_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = _utc_now()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_status(self, job_id: str) -> dict[str, Any] | None:
        path = self._status_path(job_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def start_generate(
        self,
        job_id: str,
        task_type: str,
        query: str,
        source_dir: Path,
        output_dir: Path,
        api_key: str = "",
    ) -> None:
        self._start_job(
            job_id=job_id,
            job_mode="generate",
            task_type=task_type,
            kwargs={
                "query": query,
                "source_dir": source_dir,
                "output_dir": output_dir,
                "api_key": api_key,
            },
        )

    def start_score(
        self,
        job_id: str,
        task_type: str,
        task_path: Path,
        report_path: Path,
        output_dir: Path,
        source_dir: Path | None = None,
        api_key: str = "",
        max_report_chars: int = 0,
    ) -> None:
        self._start_job(
            job_id=job_id,
            job_mode="score",
            task_type=task_type,
            kwargs={
                "task_path": task_path,
                "report_path": report_path,
                "output_dir": output_dir,
                "source_dir": source_dir,
                "api_key": api_key,
                "max_report_chars": max_report_chars,
            },
        )

    def start_impact(
        self,
        job_id: str,
        source_dir: Path,
        output_dir: Path,
        api_key: str = "",
        preloaded_rubrics: dict[str, dict[str, Path | None]] | None = None,
    ) -> None:
        """启动影响力预测任务（纯 Python，不通过子进程）。"""
        started_at = _utc_now()
        started_ts = time.time()

        self._write_status(
            job_id,
            {
                "job_id": job_id,
                "job_mode": "impact",
                "status": "running",
                "progress": 2,
                "message": "任务已启动，正在准备…",
                "task_type": "impact_full",
                "label": IMPACT_LABEL,
                "mode_label": "科学影响力预测",
                "started_at": started_at,
                "started_ts": started_ts,
                "updated_at": started_at,
                "logs": [],
            },
        )

        thread = threading.Thread(
            target=self._run_impact,
            args=(job_id, source_dir, output_dir, api_key, started_at, started_ts),
            kwargs={"preloaded_rubrics": preloaded_rubrics or {}},
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread
        thread.start()

    def start(self, **kwargs) -> None:
        """向后兼容：等同 start_generate。"""
        self.start_generate(**kwargs)

    def _start_job(
        self,
        job_id: str,
        job_mode: str,
        task_type: str,
        kwargs: dict[str, Any],
    ) -> None:
        started_at = _utc_now()
        started_ts = time.time()
        label = PACKAGES[task_type]["label"]
        mode_label = "生成评分表" if job_mode == "generate" else "报告打分"

        self._write_status(
            job_id,
            {
                "job_id": job_id,
                "job_mode": job_mode,
                "status": "running",
                "progress": 2,
                "message": "任务已启动，正在准备…",
                "task_type": task_type,
                "label": label,
                "mode_label": mode_label,
                "started_at": started_at,
                "started_ts": started_ts,
                "updated_at": started_at,
                "logs": [],
            },
        )

        thread = threading.Thread(
            target=self._run,
            args=(job_id, job_mode, task_type, kwargs, started_at, started_ts),
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread
        thread.start()

    def _run_impact(
        self,
        job_id: str,
        source_dir: Path,
        output_dir: Path,
        api_key: str,
        started_at: str,
        started_ts: float,
        preloaded_rubrics: dict[str, dict[str, Path | None]] | None = None,
    ) -> None:
        """影响力预测的独立运行逻辑（不通过子进程）。"""
        logs: list[str] = []
        progress = 2

        def _update(msg: str, pct: int):
            nonlocal progress
            progress = max(progress, pct)
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": "impact",
                    "status": "running",
                    "progress": pct,
                    "message": msg,
                    "task_type": "impact_only",
                    "label": IMPACT_LABEL,
                    "mode_label": "科学影响力预测",
                    "started_at": started_at,
                    "logs": logs[-MAX_LOG_LINES:],
                },
            )

        try:
            # Step 1: 提取 DOI/标题
            _update("从 PDF 提取 DOI 和标题…", 10)
            ROOT_DIR = Path(__file__).resolve().parent.parent
            # 将 common 的父目录加入 sys.path，使 "from common.xxx" 可用
            if str(ROOT_DIR) not in sys.path:
                sys.path.insert(0, str(ROOT_DIR))
            from common.doi_extractor import extract_doi, extract_title

            pdf_files = list(source_dir.glob("*.pdf"))
            if not pdf_files:
                raise FileNotFoundError("未找到 PDF 文件")

            pdf_path = pdf_files[0]
            doi = extract_doi(pdf_path)
            title = extract_title(pdf_path)
            logs.append(f"PDF: {pdf_path.name}")
            if doi:
                logs.append(f"DOI: {doi}")
            if title:
                logs.append(f"Title: {title[:80]}")
            _update("DOI/标题提取完成", 25)

            # Step 2: 获取元数据
            _update("从 OpenAlex 获取论文元数据…", 30)
            from common.metadata_fetcher import fetch_work_by_doi, fetch_work_by_title

            metadata = None
            if doi:
                metadata = fetch_work_by_doi(doi)
                logs.append(f"OpenAlex: 按 DOI 查询{'成功' if metadata else '未找到'}")
            if not metadata and title:
                metadata = fetch_work_by_title(title)
                logs.append(f"OpenAlex: 按标题查询{'成功' if metadata else '未找到'}")

            if not metadata:
                _update("元数据获取失败，无法评估影响力", 90)
                elapsed = time.time() - started_ts
                self._write_status(
                    job_id,
                    {
                        "job_id": job_id,
                        "job_mode": "impact",
                        "status": "failed",
                        "progress": 90,
                        "message": "无法获取论文元数据（DOI 提取失败且标题匹配失败）",
                        "task_type": "impact_only",
                        "label": IMPACT_LABEL,
                        "started_at": started_at,
                        "elapsed_sec": round(elapsed),
                        "error": "请确认上传的是正式发表的论文 PDF（包含 DOI）",
                        "logs": logs,
                        "doi": doi,
                        "title": title,
                    },
                )
                return

            logs.append(f"Venue: {metadata.get('host_venue', 'Unknown')}")
            logs.append(f"Citations: {metadata.get('cited_by_count', 0)}")
            logs.append(f"Year: {metadata.get('publication_year', 'Unknown')}")
            _update("元数据获取成功", 35)

            # Step 2b-prep: 获取 API key（评分表生成和打分都需要）
            effective_api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
            if not effective_api_key:
                env_candidates = [
                    ROOT_DIR / ".env",
                    ROOT_DIR / "rubric-auto-gen" / ".env",
                    ROOT_DIR / "rubric-auto-gen-2" / ".env",
                    ROOT_DIR / "rubric-auto-gen-3" / ".env",
                ]
                for env_path in env_candidates:
                    if env_path.exists():
                        for line in env_path.read_text(encoding="utf-8").splitlines():
                            line = line.strip()
                            if line.startswith("DASHSCOPE_API_KEY="):
                                effective_api_key = line.split("=", 1)[1].strip().strip("'\"")
                                break
                    if effective_api_key:
                        break

            # Step 2b: 对三种任务类型生成评分表并打分（内容质量评估）
            _update("正在生成评分表并打分…", 40)
            import fitz  # PyMuPDF

            # 从 PDF 提取纯文本作为"报告"用于打分
            pdf_text = ""
            try:
                doc = fitz.open(str(pdf_path))
                for page in doc:
                    pdf_text += page.get_text("text")
                doc.close()
            except Exception as e:
                logs.append(f"PDF 文本提取失败: {e}")

            if pdf_text:
                report_text_path = output_dir / "paper_text.txt"
                report_text_path.write_text(pdf_text, encoding="utf-8")

            # 三种任务类型
            content_scores = []  # [{task_type, score_percentage, raw_score, total_score}]

            from web.runner import build_generate_command, build_score_command, scores_output_path, PACKAGES
            import concurrent.futures

            def _generate_and_score(tt: str) -> dict | None:
                """单个任务类型的处理：已上传则直接使用，未上传则生成+打分。"""
                preloaded = (preloaded_rubrics or {}).get(tt, {})
                tt_output = output_dir / tt
                tt_output.mkdir(parents=True, exist_ok=True)

                # 情况1：已上传 rubric_scores.json → 直接使用
                pre_scores = preloaded.get("scores")
                if pre_scores and pre_scores.exists():
                    try:
                        scores_data = json.loads(pre_scores.read_text(encoding="utf-8"))
                        # 复制到 output 目录
                        import shutil
                        tt_score_output = tt_output / "self_check"
                        tt_score_output.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(pre_scores), str(tt_score_output / "rubric_scores.json"))
                        # 如果有 task.json 也复制
                        pre_task = preloaded.get("task")
                        if pre_task and pre_task.exists():
                            shutil.copy2(str(pre_task), str(tt_output / "task.json"))
                        logs.append(f"[{tt}] 使用上传的打分结果: {scores_data.get('raw_score', 0)}/{scores_data.get('total_score', 0)}")
                        return {
                            "task_type": tt,
                            "label": PACKAGES[tt]["label"],
                            "score_percentage": scores_data.get("score_percentage", 0),
                            "raw_score": scores_data.get("raw_score", 0),
                            "total_score": scores_data.get("total_score", 1),
                            "dimension_scores": scores_data.get("dimension_scores", []),
                        }
                    except Exception as e:
                        logs.append(f"[{tt}] 读取上传的打分结果失败: {e}")
                        # 降级为生成

                # 情况2：已上传 task.json 但没打分 → 直接打分
                pre_task = preloaded.get("task")
                if pre_task and pre_task.exists():
                    try:
                        import shutil
                        shutil.copy2(str(pre_task), str(tt_output / "task.json"))
                        logs.append(f"[{tt}] 使用上传的 task.json，开始打分")

                        _update(f"对 {PACKAGES[tt]['label']} 打分…", 50)
                        tt_score_output = tt_output / "self_check"
                        tt_score_output.mkdir(parents=True, exist_ok=True)

                        score_cmd, score_env = build_score_command(
                            tt, tt_output / "task.json", report_text_path,
                            tt_score_output, source_dir, effective_api_key,
                            quiet=True,
                        )
                        score_proc = subprocess.run(
                            score_cmd, cwd=str(ROOT_DIR),
                            env=score_env,
                            capture_output=True, text=True, timeout=600,
                        )
                        score_logs = (score_proc.stdout or "") + (score_proc.stderr or "")
                        for line in score_logs.strip().splitlines():
                            clean = line.strip()
                            if clean:
                                logs.append(f"[{tt}] {clean}")

                        sp = scores_output_path(tt, tt_score_output)
                        if sp.exists():
                            scores_data = json.loads(sp.read_text(encoding="utf-8"))
                            logs.append(f"[{tt}] 打分完成: {scores_data.get('raw_score', 0)}/{scores_data.get('total_score', 0)}")
                            return {
                                "task_type": tt,
                                "label": PACKAGES[tt]["label"],
                                "score_percentage": scores_data.get("score_percentage", 0),
                                "raw_score": scores_data.get("raw_score", 0),
                                "total_score": scores_data.get("total_score", 1),
                                "dimension_scores": scores_data.get("dimension_scores", []),
                            }
                        else:
                            logs.append(f"[{tt}] rubric_scores.json 未生成")
                            return None
                    except subprocess.TimeoutExpired:
                        logs.append(f"[{tt}] 打分超时（600秒）")
                        return None
                    except Exception as e:
                        logs.append(f"[{tt}] 打分异常: {e}")
                        return None

                # 情况3：什么都没上传 → 生成+打分
                try:
                    _update(f"生成 {PACKAGES[tt]['label']} 评分表…", 40)

                    gen_cmd, gen_env = build_generate_command(
                        tt, "", source_dir, tt_output, effective_api_key, quiet=True,
                    )
                    gen_proc = subprocess.run(
                        gen_cmd, cwd=str(ROOT_DIR),
                        env=gen_env,
                        capture_output=True, text=True, timeout=600,
                    )
                    gen_logs = (gen_proc.stdout or "") + (gen_proc.stderr or "")
                    for line in gen_logs.strip().splitlines():
                        clean = line.strip()
                        if clean:
                            logs.append(f"[{tt}] {clean}")
                    if gen_proc.returncode != 0:
                        logs.append(f"[{tt}] 评分表生成失败 (exit {gen_proc.returncode})")
                        return None

                    task_path = tt_output / "task.json"
                    if not task_path.exists():
                        logs.append(f"[{tt}] task.json 未生成")
                        return None

                    _update(f"对 {PACKAGES[tt]['label']} 打分…", 50)
                    tt_score_output = tt_output / "self_check"
                    tt_score_output.mkdir(parents=True, exist_ok=True)

                    score_cmd, score_env = build_score_command(
                        tt, task_path, report_text_path,
                        tt_score_output, source_dir, effective_api_key,
                        quiet=True,
                    )
                    score_proc = subprocess.run(
                        score_cmd, cwd=str(ROOT_DIR),
                        env=score_env,
                        capture_output=True, text=True, timeout=600,
                    )
                    score_logs = (score_proc.stdout or "") + (score_proc.stderr or "")
                    for line in score_logs.strip().splitlines():
                        clean = line.strip()
                        if clean:
                            logs.append(f"[{tt}] {clean}")

                    sp = scores_output_path(tt, tt_score_output)
                    if sp.exists():
                        scores_data = json.loads(sp.read_text(encoding="utf-8"))
                        logs.append(f"[{tt}] 打分完成: {scores_data.get('raw_score', 0)}/{scores_data.get('total_score', 0)}")
                        return {
                            "task_type": tt,
                            "label": PACKAGES[tt]["label"],
                            "score_percentage": scores_data.get("score_percentage", 0),
                            "raw_score": scores_data.get("raw_score", 0),
                            "total_score": scores_data.get("total_score", 1),
                            "dimension_scores": scores_data.get("dimension_scores", []),
                        }
                    else:
                        logs.append(f"[{tt}] rubric_scores.json 未生成")
                        return None
                except subprocess.TimeoutExpired:
                    logs.append(f"[{tt}] 超时（600秒）")
                    return None
                except Exception as e:
                    logs.append(f"[{tt}] 异常: {e}")
                    return None

            # 并行执行 3 种任务类型
            _update("正在生成评分表并打分（并行）…", 40)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(_generate_and_score, tt): tt for tt in ["literature_review", "data_analysis", "claim_verification"]}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        content_scores.append(result)

            # 计算内容质量分（满分 170）
            # 找出最高一项
            content_details = list(content_scores)
            best_pct = 0.0
            for cs in content_scores:
                if cs.get("score_percentage", 0) > best_pct:
                    best_pct = cs["score_percentage"]

            logs.append(f"内容质量（最高项）: {best_pct:.1f}%")
            _update("评分表打分完成", 60)

            # Step 3: LLM 影响力评估
            _update("LLM 正在评估影响力…", 60)
            from common.impact_evaluator import evaluate_impact
            from openai import OpenAI

            # effective_api_key 已在 Step 2b-prep 中获取
            if not effective_api_key:
                raise ValueError("未找到 DASHSCOPE_API_KEY")

            DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            client = OpenAI(api_key=effective_api_key, base_url=DASHSCOPE_BASE_URL, timeout=120)

            impact = evaluate_impact(metadata, client)
            if impact:
                logs.append(f"Impact score: {impact.get('total_score', 0)}/30")
                logs.append(f"Impact level: {impact.get('impact_level', 'Unknown')}")
            else:
                logs.append("LLM 影响力评估失败")
            _update("影响力评估完成", 85)

            # Step 4: 组合评级（百分制）
            _update("生成评级报告…", 90)
            from common.composite_scorer import calculate_composite_rating

            impact_score = impact.get("total_score") if impact else None
            rating = calculate_composite_rating(
                content_details=content_details,
                impact_score=impact_score,
            )

            composite_pct = rating.get("composite_score", 0)
            logs.append(f"总分: {composite_pct}% ({rating.get('rating')})")

            # Step 5: 偏差解释
            _update("生成偏差解释…", 95)
            from common.impact_explainer import explain_impact_bias

            bias_explanation = None
            if impact and metadata:
                bias_explanation = explain_impact_bias(impact, metadata, client)
                if bias_explanation:
                    logs.append("偏差解释生成成功")
                else:
                    logs.append("偏差解释生成失败")
            else:
                logs.append("偏差解释跳过（缺少 impact 或 metadata）")

            # 保存结果
            result = {
                "pdf_file": pdf_path.name,
                "doi": doi,
                "title": title,
                "metadata": metadata,
                "impact": impact,
                "content_quality": {
                    "best_pct": round(best_pct, 2),
                    "details": content_details,
                },
                "rating": rating,
                "bias_explanation": bias_explanation,
            }
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "impact_report.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            elapsed = time.time() - started_ts
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": "impact",
                    "status": "completed",
                    "progress": 100,
                    "message": "影响力预测完成",
                    "task_type": "impact_full",
                    "label": IMPACT_LABEL,
                    "mode_label": "科学影响力预测",
                    "started_at": started_at,
                    "elapsed_sec": round(elapsed),
                    "download_url": f"/api/download/{job_id}/impact",
                    "rating": rating,
                    "total_score": composite_pct,
                    "content_quality": {
                        "best_pct": round(best_pct, 1),
                        "details": content_details,
                    },
                    "impact_score": impact_score,
                    "impact_max": 30,
                    "bias_explanation": bias_explanation,
                    "metadata_summary": {
                        "title": metadata.get("title", ""),
                        "venue": metadata.get("host_venue", ""),
                        "year": metadata.get("publication_year"),
                        "citations": metadata.get("cited_by_count", 0),
                    },
                    "logs": logs,
                },
            )

        except Exception as e:
            elapsed = time.time() - started_ts
            logs.append(f"Error: {str(e)}")
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": "impact",
                    "status": "failed",
                    "progress": progress,
                    "message": "影响力预测失败",
                    "task_type": "impact_only",
                    "label": IMPACT_LABEL,
                    "started_at": started_at,
                    "elapsed_sec": round(elapsed),
                    "error": str(e),
                    "logs": logs,
                },
            )

    def _run(
        self,
        job_id: str,
        job_mode: str,
        task_type: str,
        kwargs: dict[str, Any],
        started_at: str,
        started_ts: float,
    ) -> None:
        status = self.read_status(job_id) or {}
        logs: list[str] = list(status.get("logs", []))
        progress = int(status.get("progress", 2))
        message = status.get("message", "正在处理…")
        label = PACKAGES[task_type]["label"]

        pkg = PACKAGES[task_type]
        if job_mode == "generate":
            cmd, env = build_generate_command(
                task_type,
                kwargs["query"],
                kwargs["source_dir"],
                kwargs["output_dir"],
                kwargs.get("api_key", ""),
                quiet=False,
            )
            result_path = kwargs["output_dir"] / "task.json"
        else:
            cmd, env = build_score_command(
                task_type,
                kwargs["task_path"],
                kwargs["report_path"],
                kwargs["output_dir"],
                kwargs.get("source_dir"),
                kwargs.get("api_key", ""),
                max_report_chars=int(kwargs.get("max_report_chars") or 0),
                quiet=False,
            )
            result_path = scores_output_path(task_type, kwargs["output_dir"])

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(pkg["dir"]),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as e:
            self._write_status(
                job_id,
                {
                    **status,
                    "job_mode": job_mode,
                    "status": "failed",
                    "progress": progress,
                    "message": "启动进程失败",
                    "error": str(e),
                    "started_at": started_at,
                    "logs": logs[-MAX_LOG_LINES:],
                },
            )
            return

        assert proc.stdout is not None
        for raw in proc.stdout:
            clean = _clean_log_line(raw)
            if not clean:
                continue
            logs.append(clean)
            if len(logs) > MAX_LOG_LINES:
                logs = logs[-MAX_LOG_LINES:]
            progress, stage_msg = _progress_from_line(clean, progress, job_mode)
            if stage_msg:
                message = stage_msg
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": job_mode,
                    "status": "running",
                    "progress": progress,
                    "message": message,
                    "task_type": task_type,
                    "label": label,
                    "mode_label": status.get("mode_label"),
                    "started_at": started_at,
                    "logs": logs,
                },
            )

        proc.wait()
        elapsed = time.time() - started_ts

        if proc.returncode != 0 or not result_path.exists():
            tail = "\n".join(logs[-8:]) or ("生成失败" if job_mode == "generate" else "评分失败")
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": job_mode,
                    "status": "failed",
                    "progress": progress,
                    "message": "生成失败" if job_mode == "generate" else "评分失败",
                    "task_type": task_type,
                    "label": label,
                    "started_at": started_at,
                    "elapsed_sec": round(elapsed),
                    "error": tail[-2000:],
                    "logs": logs,
                },
            )
            return

        if job_mode == "generate":
            result = json.loads(result_path.read_text(encoding="utf-8"))
            rubrics = result.get("rubrics", {})
            total = rubrics.get("total_score", 0)
            item_count = sum(len(d.get("items", [])) for d in rubrics.get("dimensions", []))
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": "generate",
                    "status": "completed",
                    "progress": 100,
                    "message": "生成完成",
                    "task_type": task_type,
                    "label": label,
                    "mode_label": "生成评分表",
                    "started_at": started_at,
                    "elapsed_sec": round(elapsed),
                    "total_score": total,
                    "item_count": item_count,
                    "download_url": f"/api/download/{job_id}",
                    "logs": logs,
                },
            )
        else:
            scores = json.loads(result_path.read_text(encoding="utf-8"))
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": "score",
                    "status": "completed",
                    "progress": 100,
                    "message": "评分完成",
                    "task_type": task_type,
                    "label": label,
                    "mode_label": "报告打分",
                    "started_at": started_at,
                    "elapsed_sec": round(elapsed),
                    "raw_score": scores.get("raw_score"),
                    "total_score": scores.get("total_score"),
                    "score_percentage": scores.get("score_percentage"),
                    "download_url": f"/api/download/{job_id}/scores",
                    "logs": logs,
                },
            )
