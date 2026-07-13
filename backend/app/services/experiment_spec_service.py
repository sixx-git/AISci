"""实验设计结构化契约 — 字段校验、默认推断、与 data_requirements 对齐。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.tabular_encoding_utils import _OUTCOME_NAME_HINTS


def normalize_experiment_spec(raw: Any) -> Dict[str, Any]:
    """将 LLM/规则输出的 spec 规范为固定结构。"""
    if not isinstance(raw, dict):
        raw = {}
    baselines = _as_str_list(raw.get("baselines"))
    if not baselines:
        baselines = ["Baseline（对照）", "Proposed（本文方法）"]
    features = _as_str_list(raw.get("feature_columns"))
    secondary = _as_str_list(raw.get("secondary_metrics"))
    target = _clean_column_name(raw.get("target_column"))
    return {
        "target_column": target,
        "feature_columns": features[:40],
        "baselines": baselines[:6],
        "primary_metric": str(raw.get("primary_metric") or "accuracy").strip() or "accuracy",
        "secondary_metrics": secondary[:6],
        "split_strategy": str(raw.get("split_strategy") or "row_half").strip() or "row_half",
        "task_type": str(raw.get("task_type") or "classification").strip() or "classification",
        "encoding_notes": str(raw.get("encoding_notes") or "").strip(),
        "validation_checks": _as_str_list(raw.get("validation_checks"))[:8],
    }


def build_default_spec_from_datasets(
    project_datasets: List[Dict[str, Any]],
    hypothesis: str = "",
) -> Dict[str, Any]:
    """基于 probe 元数据推断默认可执行 spec（规则层，不调用 LLM）。"""
    columns: List[str] = []
    dtypes: Dict[str, Any] = {}
    for ds in project_datasets or []:
        if not isinstance(ds, dict):
            continue
        if ds.get("data_type", "tabular") != "tabular":
            continue
        cols = ds.get("columns") or []
        if cols:
            columns = [str(c) for c in cols]
            dtypes = ds.get("dtypes") or {}
            break

    target: Optional[str] = None
    hints = list(_OUTCOME_NAME_HINTS)
    hypo_lower = (hypothesis or "").lower()
    for token in ("carcinoma", "label", "outcome", "target", "class"):
        if token in hypo_lower and token not in hints:
            hints.insert(0, token)

    for hint in hints:
        for col in columns:
            if hint in col.lower():
                target = col
                break
        if target:
            break

    feature_columns = [c for c in columns if c != target][:30]
    task_type = "classification"
    if target and dtypes.get(target) in ("DOUBLE", "FLOAT", "INTEGER", "BIGINT", "int", "float"):
        uniq_hint = len(columns)
        if uniq_hint > 0:
            task_type = "regression"

    return normalize_experiment_spec({
        "target_column": target,
        "feature_columns": feature_columns,
        "baselines": ["Baseline（对照）", "Proposed（本文方法）"],
        "primary_metric": "accuracy" if task_type == "classification" else "rmse",
        "split_strategy": "row_half",
        "task_type": task_type,
        "encoding_notes": "分类列（present/absent、a699_240 等）沙箱会自动编码为数值",
    })


def enrich_spec_from_design(spec: Dict[str, Any], design: Dict[str, Any]) -> Dict[str, Any]:
    """用实验设计文本字段补全 spec 中缺失项。"""
    out = dict(spec)
    if not out.get("primary_metric") or out.get("primary_metric") == "accuracy":
        metrics_text = str(design.get("metrics") or "").lower()
        if "f1" in metrics_text and "accuracy" not in metrics_text:
            out["primary_metric"] = "f1_score"
        elif "auc" in metrics_text:
            out["primary_metric"] = "auc"
        elif "rmse" in metrics_text or "mse" in metrics_text:
            out["primary_metric"] = "rmse"
            out["task_type"] = "regression"

    if len(out.get("baselines") or []) < 2:
        baselines = _parse_design_list(design.get("baselines"))
        if len(baselines) >= 2:
            out["baselines"] = baselines[:6]
    return normalize_experiment_spec(out)


def validate_spec_against_datasets(
    spec: Dict[str, Any],
    project_datasets: List[Dict[str, Any]],
) -> List[str]:
    """校验 spec 字段是否存在于已上传数据集，返回 data_gap 条目。"""
    if not spec or not project_datasets:
        return []

    available: set[str] = set()
    for ds in project_datasets:
        if not isinstance(ds, dict):
            continue
        for col in ds.get("columns") or []:
            available.add(str(col))

    if not available:
        return []

    gaps: List[str] = []
    target = spec.get("target_column")
    if target and target not in available:
        gaps.append(f"experiment_spec 目标列「{target}」不在已上传数据字段中")

    missing_features = [
        c for c in (spec.get("feature_columns") or []) if c and c not in available
    ]
    if missing_features:
        preview = "、".join(missing_features[:5])
        suffix = f" 等{len(missing_features)}列" if len(missing_features) > 5 else ""
        gaps.append(f"experiment_spec 特征列缺失: {preview}{suffix}")

    if not target and not (spec.get("feature_columns") or []):
        gaps.append("experiment_spec 未指定 target_column 或 feature_columns，沙箱脚本可能无法对齐假设")

    return gaps


def slim_experiment_spec_for_storage(spec: Dict[str, Any]) -> Dict[str, Any]:
    """DB 持久化用的 spec 摘要。"""
    if not isinstance(spec, dict):
        return {}
    return {
        "target_column": spec.get("target_column"),
        "primary_metric": spec.get("primary_metric"),
        "task_type": spec.get("task_type"),
        "split_strategy": spec.get("split_strategy"),
        "baselines": (spec.get("baselines") or [])[:4],
        "feature_columns_count": len(spec.get("feature_columns") or []),
        "feature_columns_preview": (spec.get("feature_columns") or [])[:12],
        "encoding_notes": (spec.get("encoding_notes") or "")[:500],
    }


def format_spec_for_prompt(spec: Dict[str, Any]) -> str:
    """将 spec 格式化为脚本生成 prompt 片段。"""
    if not spec:
        return ""
    lines = ["【experiment_spec 结构化契约 — 脚本必须严格遵循】"]
    if spec.get("target_column"):
        lines.append(f"- 目标列: {spec['target_column']}")
    feats = spec.get("feature_columns") or []
    if feats:
        preview = ", ".join(feats[:15])
        if len(feats) > 15:
            preview += f" …共{len(feats)}列"
        lines.append(f"- 特征列: {preview}")
    baselines = spec.get("baselines") or []
    if baselines:
        lines.append(f"- 基线对比: {' vs '.join(baselines[:3])}")
    lines.append(f"- 主指标: {spec.get('primary_metric', 'accuracy')}")
    lines.append(f"- 任务类型: {spec.get('task_type', 'classification')}")
    lines.append(f"- 划分策略: {spec.get('split_strategy', 'row_half')}")
    if spec.get("encoding_notes"):
        lines.append(f"- 编码说明: {spec['encoding_notes']}")
    return "\n".join(lines)


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    for sep in (";", "；", "\n", "|"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    if " vs " in text.lower():
        return [p.strip() for p in text.split(" vs ") if p.strip()]
    return [text]


def _parse_design_list(raw: Any) -> List[str]:
    return _as_str_list(raw)


def _clean_column_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "无", "未知"):
        return None
    return text
