"""Web 端异步生成/评分/影响力预测任务与状态管理。"""
from __future__ import annotations

import json
import os
import re
import shutil
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
# 影响力流水线中单次「生成评分表 / 打分」子进程超时（秒）
SUBPROCESS_TIMEOUT_SEC = 3600


def _scientific_reasoning_item_count(task_path: Path) -> int:
    """读取 task.json 中 scientific_reasoning 评分项数量。"""
    try:
        data = json.loads(task_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    stats = ((data.get("generation_meta") or {}).get("dimension_stats") or {})
    sr = stats.get("scientific_reasoning") or {}
    if "item_count" in sr:
        try:
            return int(sr.get("item_count") or 0)
        except (TypeError, ValueError):
            pass
    dims = (data.get("rubrics") or {}).get("dimensions") or []
    if isinstance(dims, dict):
        items = (dims.get("scientific_reasoning") or {}).get("items") or []
        return len(items) if isinstance(items, list) else 0
    if isinstance(dims, list):
        for dim in dims:
            if not isinstance(dim, dict):
                continue
            did = dim.get("dimension_id") or dim.get("id")
            if did == "scientific_reasoning":
                items = dim.get("items") or []
                return len(items) if isinstance(items, list) else 0
    return 0


def resolve_rubric_save_path(raw: str, default_filename: str = "task.json") -> Path | None:
    """将用户填写的保存路径规范为最终 task.json 落盘路径。

    - 空字符串 → None（不额外保存）
    - 目录 → 目录/<default_filename>（目录不存在则创建）
    - 以 .json 结尾 → 视为文件路径
    """
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise ValueError("保存路径须为绝对路径（例如 D:\\\\rubrics 或 D:\\\\rubrics\\\\task.json）")
    if path.suffix.lower() == ".json":
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError(f"保存路径不是可用目录: {path}")
    name = (default_filename or "task.json").strip() or "task.json"
    if not name.lower().endswith(".json"):
        name = f"{name}.json"
    return (path / name).resolve()


def copy_rubric_to_save_path(result_path: Path, save_path: Path | None) -> str | None:
    """复制生成的评分表到用户指定路径；成功返回落盘绝对路径字符串。"""
    if save_path is None:
        return None
    save_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(result_path), str(save_path))
    return str(save_path)

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
            return json.loads(path.read_text(encoding="utf-8-sig"))
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
        save_path: Path | None = None,
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
                "save_path": save_path,
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
        max_report_chars: int = 200000,
        rubric_save_paths: dict[str, Path | None] | None = None,
    ) -> None:
        """启动影响力预测任务（纯 Python，不通过子进程）。"""
        started_at = _utc_now()
        started_ts = time.time()
        report_limit = max_report_chars if max_report_chars > 0 else 200000

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
            kwargs={
                "preloaded_rubrics": preloaded_rubrics or {},
                "max_report_chars": report_limit,
                "rubric_save_paths": rubric_save_paths or {},
            },
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
        max_report_chars: int = 200000,
        rubric_save_paths: dict[str, Path | None] | None = None,
    ) -> None:
        """影响力预测的独立运行逻辑（不通过子进程）。"""
        logs: list[str] = []
        progress = 2
        report_limit = max_report_chars if max_report_chars > 0 else 200000
        save_paths = rubric_save_paths or {}
        saved_paths: dict[str, str] = {}

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

            upgraded_from = metadata.get("_upgraded_from") or {}
            if upgraded_from:
                logs.append(
                    "元数据已升级到正式发表版本: "
                    f"{upgraded_from.get('doi')} (cites={upgraded_from.get('cited_by_count', 0)}) "
                    f"-> {metadata.get('doi')} (cites={metadata.get('cited_by_count', 0)}, "
                    f"venue={metadata.get('host_venue') or 'N/A'})"
                )
            logs.append(f"Venue: {metadata.get('host_venue', 'Unknown')}")
            logs.append(f"Citations: {metadata.get('cited_by_count', 0)}")
            logs.append(f"Year: {metadata.get('publication_year', 'Unknown')}")
            # 影响力评估优先使用升级后的正式 DOI
            eval_doi = metadata.get("doi") or doi
            _update("元数据获取成功", 35)

            # Step 2b-prep: 获取 API key（评分表生成和打分都需要）
            from common.api_key_resolve import resolve_dashscope_api_key

            effective_api_key, key_source = resolve_dashscope_api_key(
                api_key, package_root=ROOT_DIR
            )
            if effective_api_key:
                # 不打印 key 本身，仅记录来源便于排查 401
                logs.append(f"API Key 来源: {key_source}（长度 {len(effective_api_key)}）")
                os.environ["DASHSCOPE_API_KEY"] = effective_api_key
            else:
                logs.append(
                    "未找到可用 API Key（DASHSCOPE_API_KEY / QWEN_API_KEY）。"
                    "请在预测页填写，或配置 AISci/.env / pingfenbiao .env。"
                )

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

            from runner import build_generate_command, build_score_command, scores_output_path, PACKAGES
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
                            max_report_chars=report_limit,
                            quiet=True,
                        )
                        score_proc = subprocess.run(
                            score_cmd, cwd=str(ROOT_DIR),
                            env=score_env,
                            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SEC,
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
                        logs.append(f"[{tt}] 打分超时（{SUBPROCESS_TIMEOUT_SEC}秒）")
                        return None
                    except Exception as e:
                        logs.append(f"[{tt}] 打分异常: {e}")
                        return None

                # 情况3：什么都没上传 → 生成+打分
                try:
                    _update(f"生成 {PACKAGES[tt]['label']} 评分表…", 40)

                    task_path = tt_output / "task.json"
                    gen_ok = False
                    for gen_attempt in range(1, 3):
                        if task_path.exists():
                            try:
                                task_path.unlink()
                            except OSError:
                                pass
                        gen_cmd, gen_env = build_generate_command(
                            tt, "", source_dir, tt_output, effective_api_key, quiet=True,
                        )
                        gen_proc = subprocess.run(
                            gen_cmd, cwd=str(ROOT_DIR),
                            env=gen_env,
                            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SEC,
                        )
                        gen_logs = (gen_proc.stdout or "") + (gen_proc.stderr or "")
                        for line in gen_logs.strip().splitlines():
                            clean = line.strip()
                            if clean:
                                logs.append(f"[{tt}] {clean}")
                        if gen_proc.returncode != 0:
                            logs.append(
                                f"[{tt}] 评分表生成失败 (exit {gen_proc.returncode})"
                                f"（第 {gen_attempt}/2 次）"
                            )
                            continue
                        if not task_path.exists():
                            logs.append(f"[{tt}] task.json 未生成（第 {gen_attempt}/2 次）")
                            continue
                        sr_n = _scientific_reasoning_item_count(task_path)
                        if sr_n <= 0:
                            logs.append(
                                f"[{tt}] scientific_reasoning 为空（第 {gen_attempt}/2 次），将重试生成"
                            )
                            continue
                        gen_ok = True
                        break

                    if not gen_ok or not task_path.exists():
                        logs.append(f"[{tt}] 评分表生成失败：scientific_reasoning 维度仍为空")
                        return None

                    save_to = save_paths.get(tt)
                    if save_to is not None:
                        try:
                            dest = copy_rubric_to_save_path(task_path, Path(save_to))
                            if dest:
                                logs.append(f"[{tt}] 评分表已保存到: {dest}")
                        except OSError as exc:
                            dest = None
                            logs.append(f"[{tt}] 评分表额外保存失败: {exc}")
                    else:
                        dest = None

                    _update(f"对 {PACKAGES[tt]['label']} 打分…", 50)
                    tt_score_output = tt_output / "self_check"
                    tt_score_output.mkdir(parents=True, exist_ok=True)

                    score_cmd, score_env = build_score_command(
                        tt, task_path, report_text_path,
                        tt_score_output, source_dir, effective_api_key,
                        max_report_chars=report_limit,
                        quiet=True,
                    )
                    score_proc = subprocess.run(
                        score_cmd, cwd=str(ROOT_DIR),
                        env=score_env,
                        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SEC,
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
                        out = {
                            "task_type": tt,
                            "label": PACKAGES[tt]["label"],
                            "score_percentage": scores_data.get("score_percentage", 0),
                            "raw_score": scores_data.get("raw_score", 0),
                            "total_score": scores_data.get("total_score", 1),
                            "dimension_scores": scores_data.get("dimension_scores", []),
                        }
                        if dest:
                            out["saved_path"] = dest
                        return out
                    else:
                        logs.append(f"[{tt}] rubric_scores.json 未生成")
                        return None
                except subprocess.TimeoutExpired:
                    logs.append(f"[{tt}] 超时（{SUBPROCESS_TIMEOUT_SEC}秒）")
                    return None
                except Exception as e:
                    logs.append(f"[{tt}] 异常: {e}")
                    return None

            # 串行执行，避免三路并行抢占 LLM 导致 scientific_reasoning 超时
            _update("正在生成评分表并打分（串行）…", 40)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                futures = {executor.submit(_generate_and_score, tt): tt for tt in ["literature_review", "data_analysis", "claim_verification"]}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        saved = result.pop("saved_path", None)
                        if saved:
                            saved_paths[result["task_type"]] = saved
                        content_scores.append(result)

            # 计算内容质量分（取三种评分表最高百分比）
            # 找出最高一项
            content_details = list(content_scores)
            best_pct = 0.0
            for cs in content_scores:
                if cs.get("score_percentage", 0) > best_pct:
                    best_pct = cs["score_percentage"]

            logs.append(f"内容质量（最高项）: {best_pct:.1f}%")
            _update("评分表打分完成", 60)

            # Step 3: LLM 影响力评估（增强版，整合新技能）
            _update("LLM 正在评估影响力（增强版：引用网络+早期预测+文本特征）…", 60)
            from common.impact_evaluator import evaluate_impact

            impact = evaluate_impact(
                title=metadata.get("title", "") or (title or ""),
                doi=eval_doi or "",
                pdf_text=pdf_text,
                api_key=effective_api_key,
            )
            if impact:
                def _dim_score(block: Any, default_max: int = 10) -> tuple[float, int]:
                    if isinstance(block, dict):
                        return float(block.get("score") or 0), int(block.get("max") or default_max)
                    if isinstance(block, (int, float)):
                        return float(block), default_max
                    if isinstance(block, str):
                        text = block.strip()
                        if "/" in text:
                            left, _, right = text.partition("/")
                            try:
                                return float(left), int(float(right))
                            except ValueError:
                                pass
                        try:
                            return float(text), default_max
                        except ValueError:
                            return 0.0, default_max
                    return 0.0, default_max

                cal_total = impact.get("calibrated_total")
                if isinstance(cal_total, dict):
                    cal_score = cal_total.get("score", 0)
                else:
                    cal_score = cal_total if isinstance(cal_total, (int, float, str)) else 0
                logs.append(f"Impact calibrated score: {cal_score}/30")
                d1s, d1m = _dim_score(impact.get("d1_text_quality"), 10)
                d2s, d2m = _dim_score(impact.get("d2_reputation"), 10)
                d3s, d3m = _dim_score(impact.get("d3_future_potential"), 6)
                d4s, d4m = _dim_score(impact.get("d4_bias_fairness"), 4)
                logs.append(f"D1 文本质量: {d1s}/{d1m}")
                logs.append(f"D2 声誉影响: {d2s}/{d2m}")
                logs.append(f"D3 未来潜力: {d3s}/{d3m}")
                logs.append(f"D4 偏差公平: {d4s}/{d4m}")
                logs.append(f"预测置信度: {impact.get('prediction_confidence', 'unknown')}")
            else:
                logs.append("LLM 影响力评估失败")
            _update("影响力评估完成", 85)

            # Step 4: 组合评级（百分制）
            _update("生成评级报告…", 90)
            from common.composite_scorer import calculate_composite_rating, resolve_impact_score

            impact_score, _impact_max = resolve_impact_score(impact, None)

            rating = calculate_composite_rating(
                content_details=content_details,
                impact_score=impact_score,
            )

            composite_pct = rating.get("composite_score", 0)
            logs.append(f"总分: {composite_pct}% ({rating.get('rating')})")

            # Step 5: 增强版偏差解释
            _update("生成深度偏差解释（7维度偏差分析）…", 95)
            from common.impact_explainer import explain_prediction_bias

            bias_explanation = None
            if impact:
                bias_explanation = explain_prediction_bias(impact, api_key=effective_api_key)
                if bias_explanation:
                    logs.append("深度偏差解释生成成功")
                    fairness = bias_explanation.get("fairness_assessment")
                    if isinstance(fairness, dict):
                        logs.append(f"公平性评分: {fairness.get('overall_fairness_score', 0)}/10")
                    elif fairness is not None:
                        logs.append(f"公平性评分: {fairness}")
                else:
                    logs.append("深度偏差解释生成失败")
            else:
                logs.append("偏差解释跳过（缺少 impact）")

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
                    "saved_paths": saved_paths,
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
            saved_path: str | None = None
            save_path = kwargs.get("save_path")
            if save_path is not None:
                try:
                    saved_path = copy_rubric_to_save_path(result_path, Path(save_path))
                    if saved_path:
                        logs.append(f"评分表已保存到: {saved_path}")
                except OSError as exc:
                    logs.append(f"评分表额外保存失败: {exc}")
            self._write_status(
                job_id,
                {
                    "job_id": job_id,
                    "job_mode": "generate",
                    "status": "completed",
                    "progress": 100,
                    "message": "生成完成" if not saved_path else f"生成完成，已保存到 {saved_path}",
                    "task_type": task_type,
                    "label": label,
                    "mode_label": "生成评分表",
                    "started_at": started_at,
                    "elapsed_sec": round(elapsed),
                    "total_score": total,
                    "item_count": item_count,
                    "download_url": f"/api/download/{job_id}",
                    "saved_path": saved_path,
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
