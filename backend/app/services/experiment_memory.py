"""跨会话实验记忆（借鉴 InternAgent Task/Online Memory）。

独立 mem_store，不读写 iterative_experiments 投影；
真相源为 shaxiang 实验 dict，写入失败不影响实验执行。
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_HIGHER_IS_BETTER = {
    "accuracy", "acc", "f1", "f1_score", "auc", "auroc", "precision", "recall",
    "map", "r2", "r_squared", "bleu", "rouge", "ndcg", "silhouette",
}
_LOWER_IS_BETTER = {
    "loss", "error", "rmse", "mae", "mse", "mape", "perplexity", "wer", "cer",
}


@dataclass
class ExperimentMemoryRecord:
    record_id: str
    scope_key: str
    experiment_id: str
    title: str = ""
    hypothesis: str = ""
    research_goal: str = ""
    method_summary: str = ""
    baseline_metrics: Dict[str, float] = field(default_factory=dict)
    best_metrics: Dict[str, float] = field(default_factory=dict)
    label: int = 0  # 1 / 0 / -1
    overall_improvement_rate: float = 0.0
    primary_metric: Optional[str] = None
    success: bool = False
    status: str = ""
    timestamp: str = ""
    embedding_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentMemoryRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in (data or {}).items() if k in known}
        return cls(**payload)


def _settings():
    from app.core.config import get_settings

    s = get_settings()
    return s


def _memory_root() -> Path:
    s = _settings()
    root = Path(getattr(s, "EXPERIMENT_MEMORY_DIR", "./storage/experiment_memory") or "./storage/experiment_memory")
    if not root.is_absolute():
        # 相对 backend CWD
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _scope_dir(scope_key: str) -> Path:
    safe = re.sub(r"[^\w\-.:]+", "_", (scope_key or "default").strip())[:120] or "default"
    d = _memory_root() / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _records_path(scope_key: str) -> Path:
    return _scope_dir(scope_key) / "records.json"


def load_records(scope_key: str) -> List[ExperimentMemoryRecord]:
    path = _records_path(scope_key)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("records") or []
        return [ExperimentMemoryRecord.from_dict(x) for x in items if isinstance(x, dict)]
    except Exception as exc:
        logger.warning("[实验记忆] 读取失败 %s: %s", path, exc)
        return []


def save_records(scope_key: str, records: List[ExperimentMemoryRecord]) -> None:
    path = _records_path(scope_key)
    payload = [r.to_dict() for r in records]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _flatten_metrics(obj: Any, prefix: str = "") -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if math.isfinite(float(v)):
                out[str(k).lower()] = float(v)
                out[key.lower()] = float(v)
        elif isinstance(v, dict):
            out.update(_flatten_metrics(v, key))
    return out


def _pick_primary_metric(metrics: Dict[str, float]) -> Optional[str]:
    keys = list(metrics.keys())
    for preferred in ("accuracy", "f1", "f1_score", "auc", "rmse", "mae", "loss"):
        for k in keys:
            if k.split(".")[-1] == preferred:
                return k
    return keys[0] if keys else None


def _is_higher_better(metric: str) -> bool:
    leaf = metric.split(".")[-1].lower()
    if leaf in _LOWER_IS_BETTER:
        return False
    if leaf in _HIGHER_IS_BETTER:
        return True
    return "loss" not in leaf and "error" not in leaf


def _aggregate_metrics(
    iterations: List[Dict[str, Any]],
    mode: str,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """返回 (baseline, aggregated_best). baseline=首轮；aggregated 按 mode。"""
    series: List[Dict[str, float]] = []
    for it in iterations:
        if not isinstance(it, dict):
            continue
        m = it.get("metrics") or {}
        if not isinstance(m, dict):
            # 有时 metrics 在 result 下
            result = it.get("result") or {}
            if isinstance(result, dict):
                m = result.get("metrics") or result
        flat = _flatten_metrics(m if isinstance(m, dict) else {})
        if flat:
            series.append(flat)
    if not series:
        return {}, {}
    baseline = dict(series[0])
    if mode == "last":
        return baseline, dict(series[-1])
    if mode == "avg":
        keys = set()
        for s in series:
            keys |= set(s.keys())
        avg = {}
        for k in keys:
            vals = [s[k] for s in series if k in s]
            if vals:
                avg[k] = sum(vals) / len(vals)
        return baseline, avg
    # best: 对每个指标取最优
    keys = set()
    for s in series:
        keys |= set(s.keys())
    best: Dict[str, float] = {}
    for k in keys:
        vals = [s[k] for s in series if k in s]
        if not vals:
            continue
        best[k] = max(vals) if _is_higher_better(k) else min(vals)
    return baseline, best


def _label_from_metrics(
    baseline: Dict[str, float],
    improved: Dict[str, float],
    threshold: float,
) -> Tuple[int, float, Optional[str]]:
    primary = _pick_primary_metric(improved) or _pick_primary_metric(baseline)
    if not primary or primary not in baseline or primary not in improved:
        return 0, 0.0, primary
    b = baseline[primary]
    a = improved[primary]
    if abs(b) < 1e-12:
        rate = 0.0 if abs(a) < 1e-12 else (1.0 if a > b else -1.0)
    else:
        if _is_higher_better(primary):
            rate = (a - b) / abs(b)
        else:
            rate = (b - a) / abs(b)  # 下降为正改进
    if rate >= threshold:
        return 1, rate, primary
    if rate <= -threshold:
        return -1, rate, primary
    return 0, rate, primary


def build_record_from_shaxiang_experiment(
    experiment: Dict[str, Any],
    *,
    scope_key: str,
) -> Optional[ExperimentMemoryRecord]:
    if not isinstance(experiment, dict):
        return None
    exp_id = str(
        experiment.get("shaxiang_experiment_id")
        or experiment.get("id")
        or ""
    ).strip()
    if not exp_id:
        return None
    hypothesis = str(experiment.get("hypothesis") or "").strip()
    goal = str(experiment.get("research_goal") or "").strip()
    title = str(experiment.get("title") or "").strip() or (hypothesis[:80] if hypothesis else exp_id)

    s = _settings()
    agg = str(getattr(s, "EXPERIMENT_MEMORY_AGGREGATION", "best") or "best").lower()
    threshold = float(getattr(s, "EXPERIMENT_MEMORY_IMPROVE_THRESHOLD", 0.05) or 0.05)

    iterations = list(experiment.get("iterations") or [])
    baseline, improved = _aggregate_metrics(iterations, agg)
    label, rate, primary = _label_from_metrics(baseline, improved, threshold)

    plan = experiment.get("initial_plan") or {}
    method = ""
    if isinstance(plan, dict):
        method = str(plan.get("method") or plan.get("title") or plan.get("summary") or "")[:400]

    embed = "\n".join(
        x for x in [title, hypothesis, goal, method] if x
    )[:2000]

    return ExperimentMemoryRecord(
        record_id=f"{scope_key}_{exp_id}",
        scope_key=scope_key,
        experiment_id=exp_id,
        title=title,
        hypothesis=hypothesis,
        research_goal=goal,
        method_summary=method,
        baseline_metrics=baseline,
        best_metrics=improved,
        label=label,
        overall_improvement_rate=round(rate, 6),
        primary_metric=primary,
        success=(label == 1),
        status=str(experiment.get("status") or ""),
        timestamp=datetime.now(timezone.utc).isoformat(),
        embedding_text=embed,
    )


def upsert_record(scope_key: str, record: ExperimentMemoryRecord) -> ExperimentMemoryRecord:
    records = load_records(scope_key)
    replaced = False
    for i, r in enumerate(records):
        if r.record_id == record.record_id or r.experiment_id == record.experiment_id:
            records[i] = record
            replaced = True
            break
    if not replaced:
        records.append(record)
    save_records(scope_key, records)
    return record


def maybe_save_from_shaxiang(
    experiment: Dict[str, Any],
    *,
    scope_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """实验完成后写入记忆；关闭或失败返回 None，不抛错。"""
    try:
        s = _settings()
        if not bool(getattr(s, "EXPERIMENT_MEMORY_SAVE_ENABLED", True)):
            return None
        sk = (scope_key or experiment.get("project_id") or "default").strip() or "default"
        record = build_record_from_shaxiang_experiment(experiment, scope_key=sk)
        if not record:
            return None
        upsert_record(sk, record)
        logger.info(
            "[实验记忆] 已保存 record=%s label=%s metric=%s",
            record.record_id,
            record.label,
            record.primary_metric,
        )
        return record.to_dict()
    except Exception as exc:
        logger.warning("[实验记忆] 保存跳过: %s", exc)
        return None


def _keyword_score(query: str, text: str) -> float:
    try:
        from app.skills.evidence_reasoning._utils import score_relevance

        return float(score_relevance(query, text))
    except Exception:
        q = set(re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", (query or "").lower()))
        t = set(re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", (text or "").lower()))
        if not q or not t:
            return 0.0
        return len(q & t) / max(len(q), 1)


def _embed_texts(texts: List[str]) -> Optional[Any]:
    if not texts:
        return None
    try:
        from app.services.vector_store import get_vector_store
        import numpy as np

        emb = get_vector_store().embedding
        arr = emb.embed(texts)
        return np.asarray(arr, dtype=float)
    except Exception as exc:
        logger.debug("[实验记忆] embedding 不可用，仅关键词检索: %s", exc)
        return None


def retrieve(
    scope_key: str,
    query: str,
    *,
    top_k: Optional[int] = None,
    alpha: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Hybrid 检索：alpha=1 纯关键词，0 纯语义。"""
    s = _settings()
    if not bool(getattr(s, "EXPERIMENT_MEMORY_RETRIEVE_ENABLED", True)):
        return []
    top_k = int(top_k if top_k is not None else getattr(s, "EXPERIMENT_MEMORY_TOP_K", 5) or 5)
    alpha = float(alpha if alpha is not None else getattr(s, "EXPERIMENT_MEMORY_ALPHA", 0.5) or 0.5)
    alpha = max(0.0, min(1.0, alpha))

    records = load_records(scope_key)
    if not records or not (query or "").strip():
        return []

    kw_scores = [_keyword_score(query, r.embedding_text or r.hypothesis) for r in records]
    sem_scores = [0.0] * len(records)
    vectors = _embed_texts([query] + [r.embedding_text or r.hypothesis for r in records])
    if vectors is not None and len(vectors) == len(records) + 1:
        import numpy as np

        qv = vectors[0]
        qn = np.linalg.norm(qv) + 1e-12
        for i, dv in enumerate(vectors[1:]):
            dn = np.linalg.norm(dv) + 1e-12
            sem_scores[i] = float(np.dot(qv, dv) / (qn * dn))
            sem_scores[i] = max(0.0, sem_scores[i])

    scored: List[Tuple[float, ExperimentMemoryRecord]] = []
    for i, r in enumerate(records):
        score = alpha * kw_scores[i] + (1.0 - alpha) * sem_scores[i]
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, r in scored[: max(1, top_k)]:
        d = r.to_dict()
        d["retrieval_score"] = round(float(score), 4)
        out.append(d)
    return out


def format_guidance(records: List[Dict[str, Any]]) -> str:
    if not records:
        return ""
    worked = [r for r in records if int(r.get("label") or 0) > 0]
    failed = [r for r in records if int(r.get("label") or 0) < 0]
    neutral = [r for r in records if int(r.get("label") or 0) == 0]
    lines = ["# Historical experiment memory (cross-session)", ""]
    if worked:
        lines.append("Reference (worked):")
        for r in worked[:5]:
            lines.append(
                f"- [{r.get('primary_metric') or 'metric'} ↑] {r.get('hypothesis') or r.get('title')}"
            )
        lines.append("")
    if failed:
        lines.append("Avoid (declined / failed):")
        for r in failed[:5]:
            lines.append(
                f"- [{r.get('primary_metric') or 'metric'} ↓] {r.get('hypothesis') or r.get('title')}"
            )
        lines.append("")
    if neutral and not worked and not failed:
        lines.append("Past attempts (neutral):")
        for r in neutral[:5]:
            lines.append(f"- {r.get('hypothesis') or r.get('title')}")
        lines.append("")
    lines.append("请避免重复已失败方向；可在有效方向上做增量改进。")
    return "\n".join(lines).strip()


def retrieve_guidance(
    scope_key: str,
    query: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    try:
        s = _settings()
        if not bool(getattr(s, "EXPERIMENT_MEMORY_RETRIEVE_ENABLED", True)):
            return {"enabled": False, "records": [], "guidance": ""}
        records = retrieve(scope_key, query, **kwargs)
        guidance = format_guidance(records)
        return {
            "enabled": True,
            "scope_key": scope_key,
            "records": records,
            "guidance": guidance,
            "count": len(records),
        }
    except Exception as exc:
        logger.warning("[实验记忆] 检索跳过: %s", exc)
        return {"enabled": True, "records": [], "guidance": "", "error": str(exc)}

