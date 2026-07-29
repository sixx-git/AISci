"""从已落盘的评分表结果续跑影响力评估 + 偏差解释（跳过三种评分表打分）。

用法:
  python scripts/resume_impact_job.py b7a66817b3d6
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

from runner import IMPACT_LABEL, PACKAGES  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_content_details(job_dir: Path) -> list[dict]:
    """从已有 rubric_scores.json 复用三种内容质量分。"""
    candidates = {
        "claim_verification": [
            job_dir / "output" / "claim_verification" / "self_check" / "self_check" / "rubric_scores.json",
            job_dir / "output" / "claim_verification" / "self_check" / "rubric_scores.json",
        ],
        "data_analysis": [
            job_dir / "output" / "data_analysis" / "self_check" / "rubric_scores.json",
        ],
        "literature_review": [
            job_dir / "output" / "literature_review" / "self_check" / "rubric_scores.json",
        ],
    }
    details: list[dict] = []
    for tt, paths in candidates.items():
        path = next((p for p in paths if p.exists()), None)
        if not path:
            print(f"[skip] 缺少 {tt} 评分文件")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        details.append(
            {
                "task_type": tt,
                "label": PACKAGES[tt]["label"],
                "score_percentage": data.get("score_percentage", 0),
                "raw_score": data.get("raw_score", 0),
                "total_score": data.get("total_score", 1),
                "dimension_scores": data.get("dimension_scores", []),
            }
        )
        print(
            f"[reuse] {tt}: {data.get('raw_score')}/{data.get('total_score')} "
            f"({data.get('score_percentage')}%)"
        )
    return details


def main() -> int:
    job_id = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not job_id:
        print("用法: python scripts/resume_impact_job.py <job_id>")
        return 2

    # ROOT = .../pingfenbiao-main/pingfenbiao-main → 上两级到 AISci
    aisci_root = ROOT.parent.parent
    default_work = aisci_root / "storage" / "pingfenbiao_jobs"
    env_work = (os.environ.get("PINGFENBIAO_WORK_DIR") or "").strip()
    work_dir = Path(env_work) if env_work else default_work
    # 若环境变量指向别处但本 job 在 AISci storage，优先用 AISci
    if not (work_dir / job_id).exists() and (default_work / job_id).exists():
        work_dir = default_work

    job_dir = work_dir / job_id
    if not job_dir.exists():
        print(f"找不到任务目录: {job_dir}")
        return 1

    status_path = job_dir / "status.json"
    output_dir = job_dir / "output"
    source_dir = job_dir / "sources"
    paper_text_path = output_dir / "paper_text.txt"
    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        print("未找到 PDF")
        return 1
    if not paper_text_path.exists():
        print("未找到 paper_text.txt")
        return 1

    old_status = {}
    if status_path.exists():
        old_status = json.loads(status_path.read_text(encoding="utf-8"))
    logs = list(old_status.get("logs") or [])
    # 去掉上次错误行，追加续跑标记
    logs = [x for x in logs if not str(x).startswith("Error:")]
    logs.append("--- resume: 跳过评分表，续跑 impact + bias ---")

    content_details = _load_content_details(job_dir)
    if not content_details:
        print("没有可复用的内容评分，无法续跑")
        return 1

    best_pct = max(float(d.get("score_percentage") or 0) for d in content_details)
    logs.append(f"[resume] 内容质量（最高项）: {best_pct:.1f}%")

    from common.api_key_resolve import resolve_dashscope_api_key
    from common.doi_extractor import extract_doi, extract_title
    from common.metadata_fetcher import fetch_work_by_doi, fetch_work_by_title
    from common.impact_evaluator import evaluate_impact
    from common.impact_explainer import explain_prediction_bias
    from common.composite_scorer import calculate_composite_rating, resolve_impact_score

    pdf_path = pdf_files[0]
    doi = extract_doi(pdf_path) or "arxiv:2106.09685v2"
    title = extract_title(pdf_path) or ""
    pdf_text = paper_text_path.read_text(encoding="utf-8", errors="replace")

    metadata = None
    if doi:
        metadata = fetch_work_by_doi(doi)
        logs.append(f"[resume] OpenAlex DOI: {'成功' if metadata else '未找到'} ({doi})")
    if not metadata and title:
        metadata = fetch_work_by_title(title)
        logs.append(f"[resume] OpenAlex title: {'成功' if metadata else '未找到'}")
    if not metadata:
        print("元数据获取失败")
        return 1

    api_key, key_source = resolve_dashscope_api_key("", package_root=ROOT)
    if not api_key:
        print("未找到 API Key")
        return 1
    os.environ["DASHSCOPE_API_KEY"] = api_key
    logs.append(f"[resume] API Key: {key_source}（长度 {len(api_key)}）")
    print(f"API Key 来源: {key_source}")

    print("正在重跑 evaluate_impact（复用已有评分，不重跑三种评分表）…")
    t0 = time.time()
    impact = evaluate_impact(
        title=metadata.get("title") or title,
        doi=doi or metadata.get("doi", ""),
        pdf_text=pdf_text,
        api_key=api_key,
    )
    if not impact:
        logs.append("[resume] evaluate_impact 失败")
        status_path.write_text(
            json.dumps({**old_status, "logs": logs, "error": "resume evaluate_impact failed", "updated_at": _now()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("evaluate_impact 失败")
        return 1

    def _dim_score(block, default_max=10):
        if isinstance(block, dict):
            return float(block.get("score") or 0), int(block.get("max") or default_max)
        return 0.0, default_max

    cal_total = impact.get("calibrated_total")
    cal_score = cal_total.get("score", 0) if isinstance(cal_total, dict) else (cal_total or 0)
    logs.append(f"[resume] Impact calibrated score: {cal_score}/30")
    for key, label, mx in [
        ("d1_text_quality", "D1 文本质量", 10),
        ("d2_reputation", "D2 声誉影响", 10),
        ("d3_future_potential", "D3 未来潜力", 6),
        ("d4_bias_fairness", "D4 偏差公平", 4),
    ]:
        s, m = _dim_score(impact.get(key), mx)
        logs.append(f"[resume] {label}: {s}/{m}")
    logs.append(f"[resume] 预测置信度: {impact.get('prediction_confidence', 'unknown')}")
    print(f"impact 完成 ({time.time() - t0:.0f}s): calibrated={cal_score}/30")

    impact_score, _ = resolve_impact_score(impact, None)
    rating = calculate_composite_rating(
        content_details=content_details,
        impact_score=impact_score,
    )
    composite_pct = rating.get("composite_score", 0)
    logs.append(f"[resume] 总分: {composite_pct}% ({rating.get('rating')})")
    print(f"总分: {composite_pct}% ({rating.get('rating')})")

    print("正在生成偏差解释…")
    t1 = time.time()
    bias_explanation = explain_prediction_bias(impact, api_key=api_key)
    if bias_explanation:
        logs.append("[resume] 深度偏差解释生成成功")
        fairness = bias_explanation.get("fairness_assessment")
        if isinstance(fairness, dict):
            logs.append(f"[resume] 公平性评分: {fairness.get('overall_fairness_score', 0)}/10")
        print(f"偏差解释完成 ({time.time() - t1:.0f}s)")
    else:
        logs.append("[resume] 深度偏差解释生成失败（任务仍标记完成，评分可用）")
        print("偏差解释失败（将仍写入 completed，含评分结果）")

    result = {
        "pdf_file": pdf_path.name,
        "doi": doi,
        "title": metadata.get("title") or title,
        "metadata": metadata,
        "impact": impact,
        "content_quality": {
            "best_pct": round(best_pct, 2),
            "details": content_details,
        },
        "rating": rating,
        "bias_explanation": bias_explanation,
        "resumed_from": "post_rubric_crash",
        "resumed_at": _now(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "impact_report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {report_path}")

    started_at = old_status.get("started_at") or _now()
    started_ts = old_status.get("started_ts")
    elapsed = None
    if isinstance(started_ts, (int, float)):
        elapsed = round(time.time() - float(started_ts))
    elif old_status.get("elapsed_sec"):
        elapsed = int(old_status["elapsed_sec"]) + round(time.time() - t0)

    status = {
        "job_id": job_id,
        "job_mode": "impact",
        "status": "completed",
        "progress": 100,
        "message": "影响力预测完成（resume：复用评分表，续跑 impact+bias）",
        "task_type": "impact_full",
        "label": IMPACT_LABEL,
        "mode_label": "科学影响力预测",
        "started_at": started_at,
        "elapsed_sec": elapsed,
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
        "saved_paths": {},
        "logs": logs[-80:],
        "updated_at": _now(),
        "error": None,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"状态已更新为 completed: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
